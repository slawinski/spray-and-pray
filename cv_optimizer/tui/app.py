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
from cv_optimizer.tui.screens.modals import TextScreen, ResizeGuard, ActionsScreen
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


def _identity(text: str, width: int) -> Text:
    value = Text(text.replace("\n", " "), no_wrap=True)
    value.truncate(max(1, width), overflow="ellipsis")
    return value


def _source_name(app: dict) -> str:
    if app.get("source"):
        return app["source"]
    try:
        return urlparse(app.get("job_url") or "").hostname or "—"
    except ValueError:
        return "—"


def _readiness_compact(score: int | None) -> str:
    """Compact readiness display for narrow columns (score only, colored)."""
    if score is None:
        return "[dim]—[/]"
    color = "green" if score >= 70 else ("yellow" if score >= 40 else "red")
    return f"[{color}]{score:3d}[/]"


def _detail_field(content: Text, label: str, value: str | Text) -> None:
    content.append(f"{label}: ", style="bold")
    content.append(value).append("\n")


def _detail_section(content: Text, title: str) -> None:
    content.append(f"\n{title}\n", style="bold cyan underline")


class ApplicationTable(DataTable):
    BINDINGS = [Binding("enter", "select_cursor", "Detail")]

    def on_resize(self) -> None:
        self.app.call_after_refresh(self.app._reflow_table)


class FilterInput(Input):
    BINDINGS = [("escape", "leave_filter", "Return to list")]

    def on_focus(self) -> None:
        self.app.dashboard.add_class("filter-open")

    def action_leave_filter(self) -> None:
        self.app.leave_filter()


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
        Binding("?", "actions", "Actions"),
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
        self.operation_messages: dict[str, str] = {}
        self.latest_message = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="filter-bar"):
            yield FilterInput(placeholder="Filter by company or role...", id="filter-input")
        with Horizontal(id="body"):
            yield ApplicationTable(id="apps-table")
            with VerticalScroll(id="inspector"):
                yield Static(id="inspector-content", markup=False)
        yield Static(id="status-bar")
        yield Footer(id="shortcut-bar")
        yield ResizeGuard()

    def on_mount(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self.query_one("#status-bar", Static).update("Loading...")
        self._adapt_layout()
        self.refresh_apps()
        table.focus()

    @property
    def dashboard(self):
        return self.screen_stack[0]

    def on_resize(self) -> None:
        if self.is_mounted:
            self.call_after_refresh(self._adapt_layout)

    def _adapt_layout(self) -> None:
        self.mode = layout_mode(self.size.width, self.size.height)
        dashboard = self.dashboard
        dashboard.set_class(self.mode.short, "short")
        dashboard.set_class(self.mode.inspector, "with-inspector")
        inspector = dashboard.query_one("#inspector")
        inspector.styles.width = max(36, min(52, int(self.size.width * .32)))
        dashboard.query_one(Footer).compact = self.mode.short
        for screen in self.screen_stack:
            self._size_guard(screen)
        self.call_after_refresh(self._reflow_table)

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
        if len(self.screen_stack) > 1:
            return action in {"focus_next", "focus_previous"}
        return True

    def refresh_apps(self, select_id: int | None = None) -> None:
        selected = self._selected_app()
        select_id = select_id if select_id is not None else selected["id"] if selected else None
        old_index = self.dashboard.query_one("#apps-table", DataTable).cursor_row
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

    def _column_schema(self):
        width = self.dashboard.query_one("#apps-table", DataTable).size.width
        if self.mode.compact:
            return [("Application", max(1, width - 4))]
        return column_widths(width, *self._identity_widths)

    def _reflow_table(self) -> None:
        if not self.screen_stack:
            return
        if self._column_schema() != self._schema:
            self.render_table()
        else:
            self._restore_cursor()

    def render_table(self, select_id: int | None = None) -> None:
        if not self.screen_stack:
            return
        table = self.dashboard.query_one("#apps-table", DataTable)
        selected = self._selected_app()
        if select_id is None and selected:
            select_id = selected["id"]
        anchor = table.scroll_y
        schema = self._column_schema()
        table.clear(columns=True)
        table.show_header = not self.mode.compact
        for name, size in schema:
            table.add_column(name, width=size, key=name)
        self._schema = schema
        for idx, app in enumerate(self.filtered):
            created = app["created_at"][:10] if app["created_at"] else ""
            cv = _checkmark(app.get("cv_path"), app["id"] in self.regenerating_ids)
            cl = _checkmark(app.get("cover_letter_path"), app["id"] in self.generating_cl_ids)
            match_row = self.matches.get(app["id"])
            match_score = match_row["score"] if match_row else None
            if self.mode.compact:
                cell = _identity(app["company"], schema[0][1])
                cell.append("\n").append(_identity(app["role"], schema[0][1]))
                cell.append("\n").append(Text.from_markup(_status_rich(app["latest_status"])))
                cell.append(" · Match ").append(Text.from_markup(_match_rich(match_score)))
                cell.append("\nCV ").append(Text.from_markup(cv))
                cell.append("  CL ").append(Text.from_markup(cl)).append(f"  Added {created or '—'}")
                table.add_row(cell, height=4, key=str(app["id"]))
            else:
                values = {
                    "Company": Text(app["company"], no_wrap=True, overflow="ellipsis"),
                    "Role": Text(app["role"], no_wrap=True, overflow="ellipsis"),
                    "Status": _status_rich(app["latest_status"]), "Match": _match_rich(match_score),
                    "Readiness": _readiness_compact(self.readiness.get(app["id"])),
                    "Source": Text(_source_name(app)),
                    "Added": created, "#": str(idx + 1),
                    "CV": cv, "CL": cl, "JD": _checkmark(app.get("jd_path")),
                }
                table.add_row(*(values[name] for name, _ in schema), key=str(app["id"]))
        self._render_status()
        table.scroll_to(y=anchor, animate=False)
        if select_id is not None:
            for idx, app in enumerate(self.filtered):
                if app["id"] == select_id:
                    table.move_cursor(row=idx)
                    break
        self.call_after_refresh(self._restore_cursor)
        self._update_inspector()

    def _restore_cursor(self) -> None:
        if not self.screen_stack:
            return
        table = self.dashboard.query_one("#apps-table", DataTable)
        table.move_cursor(row=table.cursor_row, scroll=True)
        self._render_status()

    def _update_inspector(self) -> None:
        app = self._selected_app()
        content = self.detail_content(app) if app else "No application selected. / Filter · ? Actions"
        self.dashboard.query_one("#inspector-content", Static).update(content)
        for screen in self.screen_stack[1:]:
            if isinstance(screen, TextScreen) and screen.application_id is not None:
                record = self.filtered_by_id.get(screen.application_id)
                if record:
                    screen.query_one("#text-content", Static).update(self.detail_content(record))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self.screen_stack or event.data_table.id != "apps-table":
            return
        selected = self._selected_app()
        if selected and event.row_key.value == str(selected["id"]):
            self._update_inspector()
            self._render_status()

    def _render_status(self) -> None:
        table = self.dashboard.query_one("#apps-table", DataTable)
        count = f"{table.cursor_row + 1 if table.row_count else 0}/{len(self.filtered)}"
        message = self.operation_message or self.latest_message or "applications"
        self.dashboard.query_one("#status-bar", Static).update(f"{count} · {message}")

    @property
    def operation_message(self) -> str:
        return " · ".join(self.operation_messages.values())

    def _status(self, message: str, group: str) -> None:
        self.operation_messages[group] = message
        self._render_status()
        for screen in self.screen_stack[1:]:
            if isinstance(screen, TextScreen) and screen.title_text == "Operation status":
                screen.query_one("#text-content", Static).update(self.operation_content())

    def _notify(self, message: str) -> None:
        self.latest_message = message
        self._render_status()
        for screen in self.screen_stack[1:]:
            if isinstance(screen, TextScreen) and screen.title_text == "Operation status":
                screen.query_one("#text-content", Static).update(self.operation_content())

    def _finish_operation(self, message: str, group: str) -> None:
        self.operation_messages.pop(group, None)
        self._notify(message)

    def _document_ready(self, message: str, warnings: list[str]) -> None:
        note = " ".join(warnings)
        try:
            self.call_from_thread(self._finish_operation, (f"[yellow]⚠ {note}[/] " if note else "") + message, "default")
        except Exception:
            logger.warning("Document completion notification failed", exc_info=True)

    def _selected_app(self) -> dict | None:
        table = self.dashboard.query_one("#apps-table", DataTable)
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
        self._status("[bold blue]⟳[/] Scoring selected application…", "scoring")
        self._score_one(app["id"], app["company"], app["role"])

    def action_score_all_missing(self) -> None:
        """Backfill Match Scores for all applications missing one."""
        self._status("[bold blue]⟳[/] Scoring applications missing a Match…", "scoring")
        self._score_all()

    @work(exclusive=True, thread=True, group="scoring")
    def _score_one(self, app_id: int, company: str, role: str) -> None:
        from cv_optimizer.matching import MatchService

        try:
            outcome = MatchService().score_application(app_id)
            self.call_from_thread(
                self._finish_operation,
                f"[bold green]✓[/] {company} — {role}: "
                f"{outcome['score']} {outcome['label']}"
                + (" (cached)" if outcome["cached"] else ""),
                "scoring",
            )
        except Exception as e:
            self.call_from_thread(self._finish_operation, f"[red]✗[/] Match scoring failed: {e}", "scoring")
        finally:
            self.call_from_thread(self.refresh_apps)

    @work(exclusive=True, thread=True, group="scoring")
    def _score_all(self) -> None:
        from cv_optimizer.matching import MatchService

        def progress(message: str) -> None:
            self.call_from_thread(self._status, f"[bold blue]⟳[/] {message}", "scoring")

        try:
            result = MatchService().score_missing_applications(progress=progress)
            if result["scored"]:
                note = f"[bold green]✓[/] Scored {result['scored']} application(s)"
                if result["skipped_no_jd"]:
                    note += f" · {result['skipped_no_jd']} skipped (no JD)"
                if result["errors"]:
                    note += f" · {len(result['errors'])} failed"
                self.call_from_thread(self._finish_operation, note, "scoring")
            else:
                self.call_from_thread(
                    self._finish_operation, "No applications missing a Match Score.", "scoring"
                )
        except Exception as e:
            self.call_from_thread(self._finish_operation, f"[red]✗[/] Match scoring failed: {e}", "scoring")
        finally:
            self.call_from_thread(self.refresh_apps)

    def action_sankey(self) -> None:
        from cv_optimizer.sankey import generate_sankey_html
        generate_sankey_html()

    def action_terminal_funnel(self) -> None:
        from cv_optimizer.tui.screens.modals import SankeyScreen
        self.push_screen(SankeyScreen())

    def action_discover_jobs(self) -> None:
        """Launch discovery in a background worker; the UI stays responsive."""
        if not settings.enable_discovery:
            self._notify("Discovery is disabled (set ENABLE_DISCOVERY=true to enable it).")
            return
        if self.discovering:
            self._notify("[yellow]Discovery already running…[/]")
            return
        self.discovering = True
        self._status("[bold blue]Discovering jobs…[/]", "discovery")
        self._run_discovery()

    def _discovery_progress(self, message: str) -> None:
        self.call_from_thread(self._status, f"[bold blue]⟳[/] {message}", "discovery")

    @work(exclusive=True, thread=True, group="discovery")
    def _run_discovery(self) -> None:
        try:
            from cv_optimizer.discovery.config import load_config
            from cv_optimizer.discovery.lock import DiscoveryLock
            from cv_optimizer.discovery.service import DiscoveryService

            lock = DiscoveryLock()
            if not lock.acquire():
                self.call_from_thread(
                    self._finish_operation, "[yellow]Discovery already in progress.[/]", "discovery"
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
                    self._finish_operation,
                    f"[bold green]✓[/] {result.imported} new 85%+ job matches added",
                    "discovery",
                )
            else:
                self.call_from_thread(self._finish_operation, "No new 85%+ matches.", "discovery")
        except Exception as e:
            self.call_from_thread(self._finish_operation, f"[red]✗[/] Discovery failed: {e}", "discovery")
        finally:
            self.discovering = False
            self.call_from_thread(self.refresh_apps)

    def action_lessons(self) -> None:
        webbrowser.open("http://localhost:8000/learn")
        self._notify("[bold green]✓[/] Lesson library opened in browser")

    def action_refresh(self) -> None:
        self.refresh_apps()

    def action_focus_filter(self) -> None:
        self.dashboard.add_class("filter-open")
        self.call_after_refresh(self.dashboard.query_one("#filter-input", Input).focus)

    def leave_filter(self) -> None:
        self.dashboard.query_one("#apps-table", DataTable).focus()
        self.dashboard.remove_class("filter-open")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            self.leave_filter()

    def action_clear_filter(self) -> None:
        self.dashboard.query_one("#filter-input", Input).value = ""

    def available_actions(self) -> list[tuple[str, str, str, bool]]:
        global_actions = {"quit", "refresh", "focus_filter", "discover_jobs", "lessons",
                          "sankey", "score_all_missing"}
        commands = [(b.action, b.key, b.description, b.action not in global_actions)
                    for b in self.BINDINGS if b.action not in {"dismiss", "actions"}]
        commands.extend([("clear_filter", "", "Clear filter", False),
                         ("terminal_funnel", "", "Terminal funnel", False),
                         ("operation_status", "", "Operation status", False)])
        return commands

    def action_actions(self) -> None:
        def dispatch(action: str | None) -> None:
            if action:
                self.call_after_refresh(getattr(self, f"action_{action}"))
        self.push_screen(ActionsScreen(self.available_actions(), self._selected_app() is not None), dispatch)

    def action_operation_status(self) -> None:
        self.push_screen(TextScreen("Operation status", self.operation_content()))

    def operation_content(self) -> str:
        current = Text.from_markup(self.operation_message).plain if self.operation_message else "No operation in progress."
        latest = Text.from_markup(self.latest_message).plain if self.latest_message else "No completion or error yet."
        return f"Current\n{current}\n\nLatest completion / error\n{latest}"

    def action_toggle_detail(self) -> None:
        app = self._selected_app()
        if app is None:
            return
        self.push_screen(TextScreen("Application details", self.detail_content(app), application_id=app["id"]))

    def detail_content(self, app: dict) -> Text:
        readiness = self.readiness.get(app["id"])
        content = Text(overflow="fold", no_wrap=False)
        content.append(f"Application #{app['id']}\n", style="dim")
        content.append(app["company"] + "\n", style="bold")
        content.append(app["role"] + "\n")

        _detail_section(content, "Overview")
        _detail_field(content, "Status", app["latest_status"])
        _detail_field(content, "CV profile", PROFILE_LABELS.get(app.get("cv_profile"), "Not selected"))
        match = self.matches.get(app["id"])
        score = Text.from_markup(_match_rich(match["score"])) if match else Text("—")
        if match:
            score.append(f" {match['label']}")
        _detail_field(content, "Match", score)
        if match:
            _detail_field(content, "Confidence", match["confidence"])
        _detail_field(content, "Readiness", Text.from_markup(_readiness_compact(readiness)))
        content.append(self._match_detail(app))

        _detail_section(content, "Documents")
        for label, path, running in (
            ("JD", app.get("jd_path"), False),
            ("CV", app.get("cv_path"), app["id"] in self.regenerating_ids),
            ("CL", app.get("cover_letter_path"), app["id"] in self.generating_cl_ids),
        ):
            availability = Text.from_markup(_checkmark(path, running))
            availability.append(" Generating…" if running else " Available" if path else " Not available")
            _detail_field(content, label, availability)
            if path:
                content.append(f"  {path}\n", style="dim")

        _detail_section(content, "Job information")
        _detail_field(content, "Source", _source_name(app))
        _detail_field(content, "Created", app.get("created_at") or "—")
        _detail_field(content, "URL", app.get("job_url") or "N/A")
        content.append(self._discovery_detail(app))

        _detail_section(content, "Status History:")
        for entry in app["history"]:
            content.append(f"  • {entry['status']}")
            if entry.get("transitioned_at"):
                content.append(f"\n    {entry['transitioned_at']}", style="dim")
            content.append("\n")
        if not app["history"]:
            content.append("No status changes yet.\n", style="dim")
        return content

    def _match_detail(self, app: dict) -> Text:
        """Match breakdown: score, confidence, strengths, transferable
        evidence, gaps — framework transfer visibly separated from direct."""
        match_row = self.matches.get(app["id"])
        if not match_row:
            return Text()
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
        content = Text()
        if strengths or transferable or gaps:
            _detail_section(content, "Match evidence")
        for label, items, style in (("Strong", strengths[:8], "bold green"),
                                    ("Transferable", transferable[:4], "bold yellow"),
                                    ("Gaps", gaps[:8], "bold red")):
            if items:
                content.append(f"{label}:\n", style=style)
                for item in items:
                    content.append(f"  • {item}\n")
        return content

    def _discovery_detail(self, app: dict) -> Text:
        """Discovery metadata for auto-imported applications."""
        if app["id"] not in self.discovery_details:
            self.discovery_details[app["id"]] = db.get_job_posting_by_application(app["id"])
        job = self.discovery_details[app["id"]]
        if not job:
            return Text()
        content = Text()
        _detail_section(content, "Discovery")
        posted = (job.get("posted_at") or "")[:10]
        discovered = (job.get("first_seen_at") or "")[:10]
        _detail_field(content, "Posted", posted or "—")
        _detail_field(content, "Discovered", discovered or "—")
        if job.get("location_text"):
            _detail_field(content, "Location", f"{job['location_text']} ({job.get('work_model', 'unknown')})")
        if job.get("salary_raw"):
            _detail_field(content, "Salary", job["salary_raw"])
        return content

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
            self.call_from_thread(self.render_table)
            self.call_from_thread(self._status, "[bold yellow]⟳[/] Regenerating CV...", "default")
            warnings = []
            reoptimize(app["id"], on_warning=warnings.append)
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps)
            self._document_ready(f"[bold green]✓[/] CV regenerated for {app['company']} — {app['role']}", warnings)
        except Exception as e:
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.render_table)
            self.call_from_thread(self._finish_operation, f"[red]✗[/] CV regeneration failed: {e}", "default")

    @work(exclusive=True, thread=True)
    def _generate_cover_letter(self, app: dict) -> None:
        try:
            self.generating_cl_ids.add(app["id"])
            self.call_from_thread(self.render_table)
            self.call_from_thread(self._status, "[bold yellow]⟳[/] Generating cover letter...", "default")
            warnings = []
            generate_cover_letter(app["id"], on_warning=warnings.append)
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps)
            self._document_ready(f"[bold green]✓[/] Cover letter generated for {app['company']} — {app['role']}", warnings)
        except Exception as e:
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.render_table)
            self.call_from_thread(self._finish_operation, f"[red]✗[/] Cover letter generation failed: {e}", "default")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            self._notify(f"[red]✗[/] Regeneration failed")

    def action_dismiss(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return

        self.leave_filter()

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
