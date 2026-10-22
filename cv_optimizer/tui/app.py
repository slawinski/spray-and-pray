import json
import logging
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from urllib.parse import urlparse
from rich.cells import cell_len
from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import var
from textual.widgets import DataTable, Footer, Header, Input, Label, Static
from textual import work
from textual.worker import Worker, WorkerState

from cv_optimizer import db
from cv_optimizer.config import settings
from cv_optimizer.tracker import _build_app_dir, track, reoptimize, update_status, _validate_status, remove_application, generate_cover_letter, edit_application
from cv_optimizer.tui.screens.modals import ConfirmModal, SourceModal, StatusModal, EditModal, ProfileModal, PROFILE_LABELS
from cv_optimizer.tui.screens.modals import TextScreen, ResizeGuard
from cv_optimizer.tui.layout import layout_mode, column_widths

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "draft": "yellow",
    "applied": "cyan",
    "interview": "green",
    "offer": "bright_green",
    "accepted": "bold bright_green",
    "rejected": "red",
    "withdrawn": "orange3",
    "ghosted": "grey37",
}

def _status_rich(status: str) -> str:
    base = status.split()[0] if status.split()[0] in STATUS_COLORS else "applied"
    color = STATUS_COLORS.get(base, "white")
    if base == "interview":
        return f"[bold {color}]{status}[/]"
    return f"[{color}]{status}[/]"


def _match_rich(score: int | None) -> str:
    """Compact colored Match cell: 85+ bold green, 70-84 yellow,
    55-69 orange, <55 dim red, none —."""
    if score is None:
        return "[dim]—[/]"
    if score >= 85:
        color = "bold green"
    elif score >= 70:
        color = "yellow"
    elif score >= 55:
        color = "orange3"
    else:
        color = "dim red"
    return f"[{color}]{score:3d}[/]"


def _checkmark(path: str | None, regenerating: bool = False) -> str:
    if regenerating:
        return "[yellow]⟳[/]"
    return "[green]✓[/]" if path else "[dim]—[/]"


def _source_name(url: str | None, source: str | None = None) -> str:
    if source:
        return f"[bold yellow]{source}[/]"
    if not url:
        return "[dim]—[/]"
    try:
        hostname = urlparse(url).hostname or ""
        # Strip leading "www." and known prefixes for cleaner display
        hostname = hostname.removeprefix("www.")
        # Map known long hostnames to shorter labels
        known = {
            "job-boards.greenhouse.io": "greenhouse.io",
            "boards.greenhouse.io": "greenhouse.io",
        }
        return known.get(hostname, hostname)
    except Exception:
        return "[dim]—[/]"

def _identity(text: str, width: int) -> Text:
    value = Text(text.replace("\n", " "), no_wrap=True)
    value.truncate(max(1, width), overflow="ellipsis")
    return value


def _readiness_bar(score: int | None) -> str:
    if score is None:
        return "[dim]—[/]"
    filled = max(1, round(score / 10))
    empty = 10 - filled
    color = "green" if score >= 70 else ("yellow" if score >= 40 else "red")
    return f"[{color}]{'█' * filled}{'░' * empty}[/] {score:3d}"


def _readiness_compact(score: int | None) -> str:
    """Compact readiness display for narrow columns (score only, colored)."""
    if score is None:
        return "[dim]—[/]"
    color = "green" if score >= 70 else ("yellow" if score >= 40 else "red")
    return f"[{color}]{score:3d}[/]"


class ApplicationTable(DataTable):
    def on_resize(self) -> None:
        self.app.call_after_refresh(self.app.render_table)


class CvDashboard(App):
    CSS_PATH = "dashboard.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("/", "focus_filter", "Filter"),
        # Discovery is opt-in (ENABLE_DISCOVERY=true) — hidden entirely when off.
        *([Binding("J", "discover_jobs", "Discover")] if settings.enable_discovery else []),

        Binding("enter", "toggle_detail", "Detail"),
        Binding("s", "change_status", "Status"),
        Binding("e", "edit_application", "Edit"),
        Binding("v", "set_profile", "CV Profile"),
        Binding("o", "open_folder", "Open"),
        Binding("ctrl+r", "regenerate_cv", "Gen CV"),
        Binding("ctrl+g", "generate_cl", "Gen CL"),
        Binding("P", "prepare", "Prepare"),
        Binding("L", "lessons", "Lessons"),
        Binding("S", "sankey", "Sankey"),
        Binding("T", "set_source", "Source"),
        Binding("u", "open_url", "URL"),
        Binding("D", "delete_application", "Delete"),
        Binding("m", "score_match", "Score Match"),
        Binding("M", "score_all_missing", "Score All"),
        Binding("escape", "dismiss", "Dismiss"),
    ]

    filter_text = var("")

    def __init__(self) -> None:
        super().__init__()
        self.applications: list[dict] = []
        self.filtered: list[dict] = []
        self.regenerating_ids: set[int] = set()
        self.generating_cl_ids: set[int] = set()
        self.discovering: bool = False
        self.matches: dict = {}
        self.readiness: dict = {}
        self.discovery_details: dict = {}
        self.filtered_by_id: dict = {}
        self.mode = layout_mode(80, 24)
        self._schema = None
        self._identity_widths = (24, 36)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Filter by company or role...", id="filter-input")
        with Horizontal(id="body"):
            yield ApplicationTable(id="apps-table")
            with VerticalScroll(id="inspector"):
                yield Static(id="inspector-content", markup=False)
        yield Static(id="status-bar")
        yield Footer()
        yield ResizeGuard()

    def on_mount(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self.query_one("#status-bar", Static).update("Loading...")
        self._adapt_layout()
        self.refresh_apps()
        table.focus()

    def on_resize(self) -> None:
        if self.is_mounted:
            self.call_after_refresh(self._adapt_layout)

    def _adapt_layout(self) -> None:
        self.mode = layout_mode(self.size.width, self.size.height)
        dashboard = self.screen_stack[0]
        dashboard.set_class(self.mode.short, "short")
        dashboard.set_class(self.mode.inspector, "with-inspector")
        inspector = dashboard.query_one("#inspector")
        inspector.styles.width = max(36, min(52, int(self.size.width * .32)))
        for screen in self.screen_stack:
            self._size_guard(screen)
        self.call_after_refresh(self.render_table)

    def _size_guard(self, screen) -> None:
        guards = screen.query(ResizeGuard)
        if not guards:
            return
        guard = guards.first()
        undersize = self.size.width < 40 or self.size.height < 12
        if undersize and not guard.display:
            guard.previous_focus = screen.focused
            guard.display = True
            guard.focus()
        elif not undersize and guard.display:
            guard.display = False
            if guard.previous_focus is not None and guard.previous_focus.is_mounted:
                screen.set_focus(guard.previous_focus)

    def check_action(self, action, parameters):
        if self.size.width < 40 or self.size.height < 12:
            return action == "quit"
        return True

    def refresh_apps(self, select_id: int | None = None) -> None:
        selected = self._selected_app()
        select_id = select_id if select_id is not None else selected["id"] if selected else None
        old_index = self.query_one("#apps-table", DataTable).cursor_row
        try:
            applications = db.list_applications_with_status()
            matches, readiness = {}, {}
            ids = [a["id"] for a in applications]
            for start in range(0, len(ids), 500):
                batch = ids[start:start + 500]
                matches.update(db.get_latest_matches(batch))
                readiness.update(db.get_latest_readiness_batch(batch))
            self.applications = applications
            self.matches, self.readiness = matches, readiness
            self._identity_widths = (
                max((cell_len(a["company"]) for a in applications), default=24),
                max((cell_len(a["role"]) for a in applications), default=36),
            )
            self.discovery_details.clear()
            self._apply_filter()
            if select_id not in self.filtered_by_id and self.filtered:
                select_id = self.filtered[min(old_index, len(self.filtered) - 1)]["id"]
            self.render_table(select_id=select_id)
        except Exception as e:
            self._notify(f"DB error: {e}")

    def _apply_filter(self) -> None:
        """Recompute self.filtered from self.applications using filter_text."""
        text = self.filter_text.lower()
        if not text:
            self.filtered = list(self.applications)
        else:
            self.filtered = [
                a for a in self.applications
                if text in a["company"].lower() or text in a["role"].lower()
            ]
        self.filtered_by_id = {a["id"]: a for a in self.filtered}

    def render_table(self, select_id: int | None = None) -> None:
        table = self.query_one("#apps-table", DataTable)
        selected = self._selected_app()
        if select_id is None and selected:
            select_id = selected["id"]
        anchor = table.scroll_y
        width = max(1, table.size.width - 2)
        schema = [("Application", max(1, width - 2))] if self.mode.compact else column_widths(table.size.width, *self._identity_widths)
        table.clear(columns=True)
        table.show_header = not self.mode.compact
        for name, size in schema:
            table.add_column(name, width=size, key=name)
        self._schema = schema
        for idx, app in enumerate(self.filtered):
            created = app["created_at"][:10] if app["created_at"] else ""
            match_row = self.matches.get(app["id"])
            match_score = match_row["score"] if match_row else None
            if self.mode.compact:
                cell = _identity(app["company"], schema[0][1])
                cell.append("\n").append(_identity(app["role"], schema[0][1]))
                cell.append("\n").append(Text.from_markup(_status_rich(app["latest_status"])))
                cell.append(" · Match ").append(Text.from_markup(_match_rich(match_score)))
                table.add_row(cell, height=3, key=str(app["id"]))
            else:
                values = {
                    "Company": Text(app["company"], no_wrap=True, overflow="ellipsis"),
                    "Role": Text(app["role"], no_wrap=True, overflow="ellipsis"),
                    "Status": _status_rich(app["latest_status"]), "Match": _match_rich(match_score),
                    "Readiness": _readiness_compact(self.readiness.get(app["id"])),
                    "Source": Text(app.get("source") or urlparse(app.get("job_url") or "").hostname or "—"),
                    "Created": created, "#": str(idx + 1),
                    "Docs": " ".join(_checkmark(app.get(path), app["id"] in pending)
                                     for path, pending in [("jd_path", set()), ("cv_path", self.regenerating_ids),
                                                           ("cover_letter_path", self.generating_cl_ids)]),
                }
                table.add_row(*(values[name] for name, _ in schema), key=str(app["id"]))
        self._status(f"{len(self.filtered)} applications")
        table.scroll_to(y=anchor, animate=False)
        if select_id is not None:
            for idx, app in enumerate(self.filtered):
                if app["id"] == select_id:
                    table.move_cursor(row=idx)
                    break
        self.call_after_refresh(self._restore_cursor)
        self._update_inspector()

    def _restore_cursor(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.move_cursor(row=table.cursor_row, scroll=True)

    def _update_inspector(self) -> None:
        app = self._selected_app()
        content = self.detail_content(app) if app else "No application selected. / Filter · ? Actions"
        self.query_one("#inspector-content", Static).update(content)
        for screen in self.screen_stack[1:]:
            if isinstance(screen, TextScreen) and screen.application_id is not None:
                record = self.filtered_by_id.get(screen.application_id)
                if record:
                    screen.query_one("#text-content", Static).update(self.detail_content(record))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "apps-table":
            return
        selected = self._selected_app()
        if selected and event.row_key.value == str(selected["id"]):
            self._update_inspector()

    def _status(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(message)

    def _notify(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(f"[yellow]{message}[/]")

    def _document_ready(self, message: str, warnings: list[str]) -> None:
        note = " ".join(warnings)
        try:
            self.call_from_thread(self._notify, (f"[yellow]⚠ {note}[/] " if note else "") + message)
        except Exception:
            logger.warning("Document completion notification failed", exc_info=True)

    def _selected_app(self) -> dict | None:
        """Resolve identity from the mounted row key, never a result offset."""
        table = self.query_one("#apps-table", DataTable)
        if not table.row_count:
            return None
        key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return self.filtered_by_id.get(int(key.value))

    def action_delete_application(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        def on_confirm(result: bool | None) -> None:
            if not result:
                return
            try:
                remove_application(app["id"])
                self.refresh_apps()
                self._notify(f"[bold green]✓[/] Deleted {app['company']} — {app['role']}")
            except Exception as e:
                self._notify(f"[red]✗[/] {e}")

        self.push_screen(
            ConfirmModal(
                "Delete Application",
                f"Permanently delete {app['company']} — {app['role']}?\n\nThis removes all files and database records. This cannot be undone.",
            ),
            on_confirm,
        )

    def action_score_match(self) -> None:
        """Generate/refresh the Match Score for the selected application."""
        app = self._selected_app()
        if app is None:
            return
        if not app["jd_path"] or not Path(app["jd_path"]).exists():
            self._notify(f"No JD file found for application #{app['id']}")
            return
        self.run_worker(
            self._score_one,
            app["id"], app["company"], app["role"],
            exclusive=True, thread=True, group="scoring",
        )

    def action_score_all_missing(self) -> None:
        """Backfill Match Scores for all applications missing one."""
        self._notify("[bold blue]⟳[/] Scoring applications missing a Match…")
        self.run_worker(
            self._score_all, exclusive=True, thread=True, group="scoring"
        )

    @work(exclusive=True, thread=True, group="scoring")
    def _score_one(self, app_id: int, company: str, role: str) -> None:
        from cv_optimizer.matching import MatchService

        try:
            outcome = MatchService().score_application(app_id)
            self.call_from_thread(
                self._notify,
                f"[bold green]✓[/] {company} — {role}: "
                f"{outcome['score']} {outcome['label']}"
                + (" (cached)" if outcome["cached"] else ""),
            )
        except Exception as e:
            self.call_from_thread(self._notify, f"[red]✗[/] Match scoring failed: {e}")
        finally:
            self.call_from_thread(self.refresh_apps)

    @work(exclusive=True, thread=True, group="scoring")
    def _score_all(self) -> None:
        from cv_optimizer.matching import MatchService

        def progress(message: str) -> None:
            self.call_from_thread(self._status, f"[bold blue]⟳[/] {message}")

        try:
            result = MatchService().score_missing_applications(progress=progress)
            if result["scored"]:
                note = f"[bold green]✓[/] Scored {result['scored']} application(s)"
                if result["skipped_no_jd"]:
                    note += f" · {result['skipped_no_jd']} skipped (no JD)"
                if result["errors"]:
                    note += f" · {len(result['errors'])} failed"
                self.call_from_thread(self._notify, note)
            else:
                self.call_from_thread(
                    self._notify, "No applications missing a Match Score."
                )
        except Exception as e:
            self.call_from_thread(self._notify, f"[red]✗[/] Match scoring failed: {e}")
        finally:
            self.call_from_thread(self.refresh_apps)

    def action_sankey(self) -> None:
        from cv_optimizer.sankey import generate_sankey_html
        self._notify("[bold blue]⟳[/] Opening Sankey in browser...")
        generate_sankey_html()
        self._notify("[bold green]✓[/] Sankey opened in browser")

    def action_discover_jobs(self) -> None:
        """Launch discovery in a background worker; the UI stays responsive."""
        if not settings.enable_discovery:
            self._notify("Discovery is disabled (set ENABLE_DISCOVERY=true to enable it).")
            return
        if self.discovering:
            self._notify("[yellow]Discovery already running…[/]")
            return
        self.discovering = True
        self._status("[bold blue]Discovering jobs…[/]")
        self.run_worker(
            self._run_discovery, exclusive=True, thread=True, group="discovery"
        )

    def _discovery_progress(self, message: str) -> None:
        self.call_from_thread(self._status, f"[bold blue]⟳[/] {message}")

    @work(exclusive=True, thread=True, group="discovery")
    def _run_discovery(self) -> None:
        try:
            from cv_optimizer.discovery.config import load_config
            from cv_optimizer.discovery.lock import DiscoveryLock
            from cv_optimizer.discovery.service import DiscoveryService

            lock = DiscoveryLock()
            if not lock.acquire():
                self.call_from_thread(
                    self._notify, "[yellow]Discovery already in progress.[/]"
                )
                return
            try:
                config = load_config()
                service = DiscoveryService(config=config, progress=self._discovery_progress)
                result = service.run()
            finally:
                lock.release()

            if result.imported > 0:
                self.call_from_thread(
                    self._notify,
                    f"[bold green]✓[/] {result.imported} new 85%+ job matches added",
                )
            else:
                self.call_from_thread(self._notify, "No new 85%+ matches.")
        except Exception as e:
            self.call_from_thread(self._notify, f"[red]✗[/] Discovery failed: {e}")
        finally:
            self.discovering = False
            self.call_from_thread(self.refresh_apps)

    def action_lessons(self) -> None:
        webbrowser.open("http://localhost:8000/learn")
        self._notify("[bold green]✓[/] Lesson library opened in browser")

    def action_refresh(self) -> None:
        self.refresh_apps()
        self._notify("[bold green]✓[/] Refreshed")

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_toggle_detail(self) -> None:
        app = self._selected_app()
        if app is None:
            return
        self.push_screen(TextScreen("Application details", self.detail_content(app), application_id=app["id"]))

    def detail_content(self, app: dict) -> str:
        history = " → ".join(h["status"] for h in app["history"]) or "none"
        readiness = self.readiness.get(app["id"])
        return (
            f"Application #{app['id']}\n{app['company']}\n{app['role']}\n\n"
            f"Status: {app['latest_status']}\n"
            f"CV profile: {PROFILE_LABELS.get(app.get('cv_profile'), 'Not selected')}\n"
            + (self._match_detail(app) or "Match: —\n")
            + f"Readiness: {readiness if readiness is not None else '—'}\n"
            + f"Source: {app.get('source') or urlparse(app.get('job_url') or '').hostname or '—'}\n"
            + f"Created: {app.get('created_at') or '—'}\n"
            + self._discovery_detail(app)
            + f"URL: {app.get('job_url') or 'N/A'}\n"
            + f"JD: {app.get('jd_path') or 'Not available'}\n"
            + f"CV: {app.get('cv_path') or 'Not available'}\n"
            + f"CL: {app.get('cover_letter_path') or 'Not available'}\n"
            + f"Status History: {history}"
        )

    def _match_detail(self, app: dict) -> str:
        """Match breakdown: score, confidence, strengths, transferable
        evidence, gaps — framework transfer visibly separated from direct."""
        match_row = self.matches.get(app["id"])
        if not match_row:
            return ""
        lines = [
            f"Match: {match_row['score']} {match_row['label']} "
            f"(confidence {match_row['confidence']})",
        ]
        try:
            assessment = json.loads(match_row["assessment_json"])
        except (ValueError, TypeError):
            assessment = {}
        strengths = []
        transferable = []
        gaps = []
        for req in assessment.get("requirements", []):
            level = req.get("evidence_level")
            name = req.get("requirement", "?")
            if level == "direct":
                strengths.append(name)
            elif level in ("framework_transfer", "framework_depth_gap"):
                evidence = ", ".join(req.get("evidence_values") or []) or "other framework experience"
                transferable.append(f"{name} → {evidence}")
            elif level == "none":
                gaps.append(name)
        if strengths:
            lines.append("  Strong: " + "; ".join(strengths[:8]))
        if transferable:
            lines.append("  Transferable: " + " | ".join(transferable[:4]))
        if gaps:
            lines.append("  Gaps: " + "; ".join(gaps[:8]))
        return "\n".join(lines) + "\n"

    def _discovery_detail(self, app: dict) -> str:
        """Discovery metadata for auto-imported applications."""
        if app["id"] not in self.discovery_details:
            self.discovery_details[app["id"]] = db.get_job_posting_by_application(app["id"])
        job = self.discovery_details[app["id"]]
        if not job:
            return ""
        lines = ["Discovery:"]
        posted = (job.get("posted_at") or "")[:10]
        discovered = (job.get("first_seen_at") or "")[:10]
        lines.append(f"  Posted: {posted or '—'}   Discovered: {discovered or '—'}")
        if job.get("location_text"):
            lines.append(f"  Location: {job['location_text']} ({job.get('work_model', 'unknown')})")
        if job.get("salary_raw"):
            lines.append(f"  Salary: {job['salary_raw']}")
        return "\n".join(lines) + "\n"

    def action_prepare(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        if not app["jd_path"] or not Path(app["jd_path"]).exists():
            self._notify(f"No JD file found for application #{app['id']}")
            return

        self._notify(
            f"[bold blue]⟳[/] Opening interview loading screen for {app['company']}..."
        )
        webbrowser.open(
            f"http://localhost:8000/prepare-interview/{app['id']}"
        )
        self._notify("[bold green]✓[/] Loading screen opened in browser")

    def action_set_profile(self) -> None:
        app = self._selected_app()
        if app is not None:
            self._select_profile(app)

    def _select_profile(self, app: dict, on_selected=None) -> None:
        def on_profile(result: str | None) -> None:
            if result is None:
                return

            def save(confirmed: bool | None = True) -> None:
                if not confirmed:
                    return
                try:
                    db.set_application_profile(app["id"], result)
                    self.refresh_apps(select_id=app["id"])
                    self._notify(f"[bold green]✓[/] CV profile set to {PROFILE_LABELS[result]}")
                except Exception as e:
                    self._notify(f"[red]✗[/] {e}")
                    return
                if on_selected is not None:
                    on_selected()

            if app.get("cv_profile") is not None and result != app["cv_profile"]:
                self.push_screen(
                    ConfirmModal(
                        "Change CV Profile",
                        f"Change to {PROFILE_LABELS[result]}?\n\n"
                        "Existing files are kept, but both CV and cover letter will need regeneration.",
                    ),
                    save,
                )
            elif result != app.get("cv_profile"):
                save()
            elif on_selected is not None:
                on_selected()

        self.push_screen(ProfileModal(app["id"], app.get("cv_profile")), on_profile)

    def action_set_source(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        def on_source(result: str | None) -> None:
            if result == app.get("source"):
                return  # no change
            db.set_source(app["id"], result)
            self.refresh_apps(select_id=app["id"])
            label = result or "auto-detect"
            self._notify(f"[bold green]✓[/] Source set to {label}")

        self.push_screen(
            SourceModal(app["id"], app["company"], app.get("source")),
            on_source,
        )

    def action_change_status(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        def on_status(result: str | None) -> None:
            if result is None:
                return
            try:
                validated = _validate_status(result)
                update_status(app["id"], validated)
                self.refresh_apps(select_id=app["id"])
                self._notify(f"Status updated to {validated}")
            except ValueError as e:
                self._notify(str(e))

        from cv_optimizer.tui.screens.modals import StatusModal
        self.push_screen(StatusModal(app["id"], app["latest_status"]), on_status)

    def action_edit_application(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        def on_edit(result: dict | None) -> None:
            if result is None:
                return
            try:
                # The modal always returns strings — diff against current
                # values so untouched fields are left alone (None = no change).
                kwargs: dict = {}
                if result["company"].strip() != app["company"]:
                    kwargs["company"] = result["company"]
                if result["role"].strip() != app["role"]:
                    kwargs["role"] = result["role"]
                if (result["job_url"].strip() or None) != app.get("job_url"):
                    kwargs["job_url"] = result["job_url"]
                if not kwargs:
                    self._notify("No changes.")
                    return
                updated = edit_application(app["id"], **kwargs)
                self.refresh_apps(select_id=app["id"])
                self._notify(f"[bold green]✓[/] Updated {updated['company']} — {updated['role']}")
            except ValueError as e:
                self._notify(f"[red]✗[/] {e}")

        self.push_screen(
            EditModal(app["id"], app["company"], app["role"], app.get("job_url")),
            on_edit,
        )

    def action_open_folder(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        target = app["cv_path"]
        if target and Path(target).exists():
            subprocess.run(["open", "-R", target], check=False)
        else:
            app_dir = _build_app_dir(app["id"], app["company"], app["role"])
            if app_dir.exists():
                subprocess.run(["open", str(app_dir)], check=False)
            else:
                self._notify(f"CV path not found at {target}")

    def action_open_url(self) -> None:
        app = self._selected_app()
        if app is None:
            return
        url = app.get("job_url")
        if url:
            webbrowser.open(url)
            self._notify("[bold green]✓[/] Job posting opened in browser")
        else:
            self._notify("No job URL available for this application")

    def action_regenerate_cv(self) -> None:
        app = self._selected_app()
        if app is None:
            return
        if app.get("cv_profile") is None:
            self._select_profile(app, self.action_regenerate_cv)
            return

        from cv_optimizer.tui.screens.modals import ConfirmModal

        def on_confirm(result: bool | None) -> None:
            if result:
                self._regenerate(app)

        self.push_screen(
            ConfirmModal(
                "Re-generate CV",
                f"Re-generate CV for {app['company']} — {app['role']}?",
            ),
            on_confirm,
        )

    def action_generate_cl(self) -> None:
        app = self._selected_app()
        if app is None:
            return

        if not app["jd_path"] or not Path(app["jd_path"]).exists():
            self._notify(f"No JD file found for application #{app['id']}")
            return

        if app.get("cv_profile") is None:
            self._select_profile(app, self.action_generate_cl)
            return

        from cv_optimizer.tui.screens.modals import ConfirmModal

        def on_confirm(result: bool | None) -> None:
            if result:
                self._generate_cover_letter(app)

        self.push_screen(
            ConfirmModal(
                "Generate Cover Letter",
                f"Generate ATS-optimized cover letter for {app['company']} — {app['role']}?",
            ),
            on_confirm,
        )


    @work(exclusive=True, thread=True)
    def _regenerate(self, app: dict) -> None:
        try:
            if not app["jd_path"] or not Path(app["jd_path"]).exists():
                self.call_from_thread(self._notify, f"No JD file found for application #{app['id']}")
                return
            self.regenerating_ids.add(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, "[bold yellow]⟳[/] Regenerating CV...")
            warnings = []
            reoptimize(app["id"], on_warning=warnings.append)
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps, app["id"])
            self._document_ready(f"[bold green]✓[/] CV regenerated for {app['company']} — {app['role']}", warnings)
        except Exception as e:
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, f"[red]✗[/] CV regeneration failed: {e}")

    @work(exclusive=True, thread=True)
    def _generate_cover_letter(self, app: dict) -> None:
        try:
            self.generating_cl_ids.add(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, "[bold yellow]⟳[/] Generating cover letter...")
            warnings = []
            generate_cover_letter(app["id"], on_warning=warnings.append)
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps, app["id"])
            self._document_ready(f"[bold green]✓[/] Cover letter generated for {app['company']} — {app['role']}", warnings)
        except Exception as e:
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, f"[red]✗[/] Cover letter generation failed: {e}")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self._notify(f"[red]✗[/] Regeneration failed")

    def action_dismiss(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return

        self.query_one("#apps-table", DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            selected = self._selected_app()
            self.filter_text = event.value
            self._apply_filter()
            self.render_table(select_id=selected["id"] if selected and selected["id"] in self.filtered_by_id else None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_detail()


def main() -> None:
    logging.getLogger("cv_optimizer").setLevel(logging.WARNING)
    app = CvDashboard()
    app.run()
