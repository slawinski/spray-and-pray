import json
import logging
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from urllib.parse import urlparse

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import var
from textual.widgets import DataTable, Footer, Header, Input, Label, Static
from textual import work
from textual.worker import Worker, WorkerState

from cv_optimizer import db
from cv_optimizer.config import settings
from cv_optimizer.tracker import _build_app_dir, track, reoptimize, update_status, _validate_status, remove_application, generate_cover_letter, edit_application
from cv_optimizer.tui.screens.modals import ConfirmModal, SourceModal, StatusModal, EditModal, ProfileModal, PROFILE_LABELS

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

COLUMNS = [
    ("#", 4),
    ("Company", 15),
    ("Role", 28),
    ("Match", 5),
    ("Status", 14),
    ("Readiness", 5),
    ("Source", 16),
    ("Created", 10),
    ("JD", 3),
    ("CV", 3),
    ("CL", 3),
]


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

def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


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
        Binding("n", "next_page", "Next"),
        Binding("S", "sankey", "Sankey"),
        Binding("p", "prev_page", "Prev"),
        Binding("T", "set_source", "Source"),
        Binding("u", "open_url", "URL"),
        Binding("D", "delete_application", "Delete"),
        Binding("m", "score_match", "Score Match"),
        Binding("M", "score_all_missing", "Score All"),
        Binding("escape", "dismiss", "Dismiss"),
    ]

    page_size = 20
    current_page = var(0)
    filter_text = var("")

    def __init__(self) -> None:
        super().__init__()
        self.applications: list[dict] = []
        self.filtered: list[dict] = []
        self.regenerating_ids: set[int] = set()
        self.generating_cl_ids: set[int] = set()
        self.discovering: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Filter by company or role...", id="filter-input")
        yield DataTable(id="apps-table")
        yield Static(id="detail-panel")
        yield Static(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(*[c[0] for c in COLUMNS])
        self.query_one("#status-bar", Static).update("Loading...")
        self.refresh_apps()

    def refresh_apps(self, select_id: int | None = None) -> None:
        try:
            self.applications = db.list_applications_with_status()
            self._apply_filter()
            if select_id is not None:
                # Keep the page that holds the selected app so the cursor
                # stays put after an in-place row update (status, source, ...).
                self.current_page = self._page_containing(select_id)
            else:
                self.current_page = 0
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

    def _page_containing(self, app_id: int) -> int:
        """Index of the page that holds app_id in the filtered list (0 if absent)."""
        for idx, app in enumerate(self.filtered):
            if app["id"] == app_id:
                return idx // self.page_size
        return 0

    def render_table(self, select_id: int | None = None) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.clear()

        start = self.current_page * self.page_size
        end = start + self.page_size
        page = self.filtered[start:end]

        # Batch queries — never per-row lookups.
        page_ids = [app["id"] for app in page]
        matches = db.get_latest_matches(page_ids)
        readiness = db.get_latest_readiness_batch(page_ids)

        for idx, app in enumerate(page):
            created = app["created_at"][:10] if app["created_at"] else ""
            match_row = matches.get(app["id"])
            match_score = match_row["score"] if match_row else None
            table.add_row(
                str(start + idx + 1),
                _truncate(app["company"], 15),
                _truncate(app["role"], 28),
                _match_rich(match_score),
                _status_rich(app["latest_status"]),
                _readiness_compact(readiness.get(app["id"])),
                _source_name(app.get("job_url"), app.get("source")),
                created,
                _checkmark(app["jd_path"]),
                _checkmark(app["cv_path"], app["id"] in self.regenerating_ids),
                _checkmark(app.get("cover_letter_path"), app["id"] in self.generating_cl_ids),
            )

        total = len(self.filtered)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        shown = f"{start + 1}–{min(end, total)}" if total else "0"
        self._status(f"Page {self.current_page + 1}/{pages} — Showing {shown} of {total} applications")

        if select_id is not None:
            for idx, app in enumerate(page):
                if app["id"] == select_id:
                    table.move_cursor(row=idx)
                    break

    def _status(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(message)

    def _notify(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(f"[yellow]{message}[/]")

    def _selected_app(self) -> dict | None:
        """The application under the table cursor, accounting for the
        current page. The table only renders `page_size` rows per page, so
        cursor_row must be offset by the page start."""
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None:
            return None
        start = self.current_page * self.page_size
        index = start + row
        if index >= len(self.filtered):
            return None
        return self.filtered[index]

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
        panel = self.query_one("#detail-panel", Static)
        if panel.has_class("visible"):
            panel.remove_class("visible")
            panel.update("")
        else:
            last_updated = ""
            if app["history"]:
                last_updated = app["history"][-1]["transitioned_at"]
            history_str = " -> ".join(h["status"] for h in app["history"]) if app["history"] else "none"
            match_block = self._match_detail(app)
            discovery_block = self._discovery_detail(app)
            panel.update(
                f"Application #{app['id']} — {app['company']} — {app['role']}\n"
                + f"CV profile: {PROFILE_LABELS.get(app.get('cv_profile'), 'Not selected')}\n"
                + match_block
                + f"Status: {app['latest_status']} (last updated: {last_updated})\n"
                + f"Readiness: {_readiness_bar(db.get_latest_readiness(app['id']))}\n"
                + discovery_block
                + f"URL: {app['job_url'] or 'N/A'}\n"
                + f"JD: {app['jd_path'] or 'N/A'}\n"
                + f"CV: {app['cv_path'] or 'N/A'}\n"
                + f"CL: {app.get('cover_letter_path') or 'N/A'}\n"
                + f"Status History: {history_str}"
            )
            panel.add_class("visible")

    def _match_detail(self, app: dict) -> str:
        """Match breakdown: score, confidence, strengths, transferable
        evidence, gaps — framework transfer visibly separated from direct."""
        match_row = db.get_latest_matches([app["id"]]).get(app["id"])
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
        job = db.get_job_posting_by_application(app["id"])
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
                    panel = self.query_one("#detail-panel", Static)
                    if panel.has_class("visible"):
                        panel.remove_class("visible")
                        self.action_toggle_detail()
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
            reoptimize(app["id"])
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps, app["id"])
            self.call_from_thread(self._notify, f"[bold green]✓[/] CV regenerated for {app['company']} — {app['role']}")
        except Exception as e:
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, f"[red]✗[/] CV regeneration failed: {e}")

    @work(exclusive=True, thread=True)
    def _generate_cover_letter(self, app: dict) -> None:
        try:
            self.generating_cl_ids.add(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            cl_path = generate_cover_letter(app["id"])
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps, app["id"])
            self.call_from_thread(self._notify, f"[bold green]✓[/] Cover letter generated for {app['company']} — {app['role']}")
        except Exception as e:
            self.generating_cl_ids.discard(app["id"])
            self.call_from_thread(self.render_table, app["id"])
            self.call_from_thread(self._notify, f"[red]✗[/] Cover letter generation failed: {e}")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.RUNNING:
            self._notify(f"[bold yellow]⟳[/] Regenerating CV...")
        elif event.state == WorkerState.SUCCESS:
            pass  
        elif event.state == WorkerState.ERROR:
            self._notify(f"[red]✗[/] Regeneration failed")

    def action_next_page(self) -> None:
        total_pages = max(1, (len(self.filtered) + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.render_table()

    def action_prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.render_table()

    def action_dismiss(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return

        panel = self.query_one("#detail-panel", Static)
        if panel.has_class("visible"):
            panel.remove_class("visible")
            panel.update("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value
            self._apply_filter()
            self.current_page = 0
            self.render_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_detail()


def main() -> None:
    logging.getLogger("cv_optimizer").setLevel(logging.WARNING)
    app = CvDashboard()
    app.run()
