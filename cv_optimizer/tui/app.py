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
from cv_optimizer.tracker import _build_app_dir, track, reoptimize, update_status, _validate_status

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    "draft": "yellow",
    "applied": "cyan",
    "interview": "green",
    "offer": "bright_green",
    "accepted": "bold bright_green",
    "rejected": "red",
    "ghosted": "grey37",
}

COLUMNS = [
    ("#", 4),
    ("Company", 22),
    ("Role", 28),
    ("Status", 14),
    ("Readiness", 10),
    ("Source", 16),
    ("Created", 10),
    ("JD", 3),
    ("CV", 3),
]


def _status_rich(status: str) -> str:
    base = status.split()[0] if status.split()[0] in STATUS_COLORS else "applied"
    color = STATUS_COLORS.get(base, "white")
    if base == "interview":
        return f"[bold {color}]{status}[/]"
    return f"[{color}]{status}[/]"


def _checkmark(path: str | None, regenerating: bool = False) -> str:
    if regenerating:
        return "[yellow]⟳[/]"
    return "[green]✓[/]" if path else "[dim]—[/]"


def _source_name(url: str | None) -> str:
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


class CvDashboard(App):
    CSS_PATH = "dashboard.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("/", "focus_filter", "Filter"),

        Binding("enter", "toggle_detail", "Detail"),
        Binding("s", "change_status", "Status"),
        Binding("o", "open_folder", "Open"),
        Binding("ctrl+r", "regenerate_cv", "Regen"),
        Binding("P", "prepare", "Prepare"),
        Binding("L", "lessons", "Lessons"),
        Binding("n", "next_page", "Next"),
        Binding("S", "sankey", "Sankey"),
        Binding("p", "prev_page", "Prev"),
        Binding("u", "open_url", "URL"),
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

    def refresh_apps(self) -> None:
        try:
            self.applications = db.list_applications_with_status()
            self.filtered = list(self.applications)
            self.current_page = 0
            self.render_table()
        except Exception as e:
            self._notify(f"DB error: {e}")

    def render_table(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        table.clear()

        start = self.current_page * self.page_size
        end = start + self.page_size
        page = self.filtered[start:end]

        for idx, app in enumerate(page):
            created = app["created_at"][:10] if app["created_at"] else ""
            table.add_row(
                str(start + idx + 1),
                _truncate(app["company"], 22),
                _truncate(app["role"], 28),
                _status_rich(app["latest_status"]),
                _readiness_bar(db.get_latest_readiness(app["id"])),
                _source_name(app.get("job_url")),
                created,
                _checkmark(app["jd_path"]),
                _checkmark(app["cv_path"], app["id"] in self.regenerating_ids),
            )

        total = len(self.filtered)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        shown = f"{start + 1}–{min(end, total)}" if total else "0"
        self._status(f"Page {self.current_page + 1}/{pages} — Showing {shown} of {total} applications")

    def _status(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(message)

    def _notify(self, message: str) -> None:
        self.query_one("#status-bar", Static).update(f"[yellow]{message}[/]")

    def action_sankey(self) -> None:
        from cv_optimizer.sankey import generate_sankey_html
        self._notify("[bold blue]⟳[/] Opening Sankey in browser...")
        generate_sankey_html()
        self._notify("[bold green]✓[/] Sankey opened in browser")

    def action_lessons(self) -> None:
        webbrowser.open("http://localhost:8000/learn")
        self._notify("[bold green]✓[/] Lesson library opened in browser")

    def action_refresh(self) -> None:
        self.refresh_apps()
        self._notify("[bold green]✓[/] Refreshed")

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_toggle_detail(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None:
            return
        if row < len(self.filtered):
            app = self.filtered[row]
            panel = self.query_one("#detail-panel", Static)
            if panel.has_class("visible"):
                panel.remove_class("visible")
                panel.update("")
            else:
                last_updated = ""
                if app["history"]:
                    last_updated = app["history"][-1]["transitioned_at"]
                history_str = " -> ".join(h["status"] for h in app["history"]) if app["history"] else "none"
                panel.update(
                    f"Application #{app['id']} — {app['company']} — {app['role']}\n"
                    f"Status: {app['latest_status']} (last updated: {last_updated})\n"
                    f"Readiness: {_readiness_bar(db.get_latest_readiness(app['id']))}\n"
                    f"URL: {app['job_url'] or 'N/A'}\n"
                    f"JD: {app['jd_path'] or 'N/A'}\n"
                    f"CV: {app['cv_path'] or 'N/A'}\n"
                    f"Status History: {history_str}"
                )
                panel.add_class("visible")

    def action_prepare(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self.filtered):
            return
        app = self.filtered[row]

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

    def action_change_status(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self.filtered):
            return
        app = self.filtered[row]

        def on_status(result: str | None) -> None:
            if result is None:
                return
            try:
                validated = _validate_status(result)
                update_status(app["id"], validated)
                self.refresh_apps()
                self._notify(f"Status updated to {validated}")
            except ValueError as e:
                self._notify(str(e))

        from cv_optimizer.tui.screens.modals import StatusModal
        self.push_screen(StatusModal(app["id"], app["latest_status"]), on_status)

    def action_open_folder(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self.filtered):
            return
        app = self.filtered[row]

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
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self.filtered):
            return
        app = self.filtered[row]
        url = app.get("job_url")
        if url:
            webbrowser.open(url)
            self._notify("[bold green]✓[/] Job posting opened in browser")
        else:
            self._notify("No job URL available for this application")

    def action_regenerate_cv(self) -> None:
        table = self.query_one("#apps-table", DataTable)
        row = table.cursor_row
        if row is None or row >= len(self.filtered):
            return
        app = self.filtered[row]

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

    @work(exclusive=True, thread=True)
    def _regenerate(self, app: dict) -> None:
        try:
            if not app["jd_path"] or not Path(app["jd_path"]).exists():
                self.call_from_thread(self._notify, f"No JD file found for application #{app['id']}")
                return
            self.regenerating_ids.add(app["id"])
            self.call_from_thread(self.render_table)
            reoptimize(app["id"])
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.refresh_apps)
            self.call_from_thread(self._notify, f"[bold green]✓[/] CV regenerated for {app['company']} — {app['role']}")
        except Exception as e:
            self.regenerating_ids.discard(app["id"])
            self.call_from_thread(self.render_table)
            self.call_from_thread(self._notify, f"[red]✗[/] CV regeneration failed: {e}")

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
            text = event.value.lower()
            if not text:
                self.filtered = list(self.applications)
            else:
                self.filtered = [
                    a for a in self.applications
                    if text in a["company"].lower() or text in a["role"].lower()
                ]
            self.current_page = 0
            self.render_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_detail()


def main() -> None:
    logging.getLogger("cv_optimizer").setLevel(logging.WARNING)
    app = CvDashboard()
    app.run()
