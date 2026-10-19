import re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from cv_optimizer import db

BASE_STATUSES = ["draft", "applied", "ghosted", "withdrawn", "rejected", "offer", "accepted"]
PROFILE_LABELS = {"it": "IT", "mechanical_engineering": "Mechanical Engineering"}


class ProfileModal(ModalScreen[str]):
    """None is cancellation; a blank selection cannot be confirmed."""

    BINDINGS = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    ProfileModal #profile-modal {
        width: 50;
        max-width: 100%;
        height: auto;
        border: thick $primary;
        padding: 1 2;
        background: $surface;
    }
    ProfileModal Horizontal { height: 3; align: center middle; }
    ProfileModal Button { margin: 0 1; min-width: 10; }
    ProfileModal Label { margin-bottom: 1; }
    """

    def __init__(self, app_id: int, current_profile: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.current_profile = current_profile

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"CV profile for Application #{self.app_id}"),
            Select([(label, name) for name, label in PROFILE_LABELS.items()],
                   id="profile-select", prompt="Select a profile...",
                   value=self.current_profile if self.current_profile else Select.NULL),
            Horizontal(
                Button("Confirm", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ),
            id="profile-modal",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            select = self.query_one("#profile-select", Select)
            if select.is_blank():
                select.focus()
                return
            self.dismiss(str(select.value))
        else:
            self.dismiss(None)


def _next_interview(history: list[dict]) -> int:
    nums = []
    for h in history:
        m = re.match(r"^interview (\d+)$", h["status"])
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


class StatusModal(ModalScreen[str]):
    def __init__(self, app_id: int, current_status: str) -> None:
        super().__init__()
        self.app_id = app_id
        self.current_status = current_status

    def compose(self) -> ComposeResult:
        app = db.get_application(self.app_id)
        history = []
        if app:
            apps = db.list_applications_with_status()
            for a in apps:
                if a["id"] == self.app_id:
                    history = a["history"]
                    break

        next_num = _next_interview(history)
        options = [(s, s) for s in BASE_STATUSES] + [(f"interview {next_num}", f"interview {next_num}")]

        if self.current_status not in {opt[0] for opt in options}:
            options.append((self.current_status, self.current_status))

        yield Vertical(
            Label(f"Change status for Application #{self.app_id}"),
            Select(options, id="status-select", prompt="Select new status...", value=self.current_status),
            Horizontal(
                Button("Confirm", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ),
            id="status-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            select = self.query_one("#status-select", Select)
            self.dismiss(select.value)
        else:
            self.dismiss(None)

    def on_select_changed(self, event: Select.Changed) -> None:
        self.current_status = str(event.value) if event.value else self.current_status


class SankeyScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        from cv_optimizer.sankey import generate_sankey

        yield ScrollableContainer(
            Static(generate_sankey(), id="sankey-content"),
            id="sankey-container",
        )

    def on_mount(self) -> None:
        self.query_one("#sankey-container").border_title = "Application Funnel"
        self.query_one("#sankey-container").border_subtitle = "Press escape to close"

    def key_escape(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.modal_title = title
        self.modal_message = message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.modal_title, id="confirm-title"),
            Label(self.modal_message, id="confirm-message"),
            Horizontal(
                Button("Yes", id="yes", variant="primary"),
                Button("No", id="no"),
            ),
            id="confirm-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class SourceModal(ModalScreen[str]):
    """Lets the user override the JD source for an application."""

    def __init__(self, app_id: int, company: str, current_source: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.company = company
        self.current_source = current_source

    def compose(self) -> ComposeResult:
        current_label = f"Current: {self.current_source}" if self.current_source else "Current: auto-detect"
        yield Vertical(
            Label(f"Set source for {self.company} (App #{self.app_id})"),
            Label(current_label, id="current-source"),
            Horizontal(
                Button("Referral", id="referral", variant="primary"),
                Button("Recruiter", id="recruiter", variant="primary"),
            ),
            Horizontal(
                Button("Clear (auto-detect)", id="clear"),
                Button("Cancel", id="cancel"),
            ),
            id="confirm-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "referral":
            self.dismiss("referral")
        elif event.button.id == "recruiter":
            self.dismiss("recruiter")
        elif event.button.id == "clear":
            self.dismiss(None)
        else:
            self.dismiss(self.current_source)  # cancel — keep current


class EditModal(ModalScreen[dict]):
    """Corrects company/role/job URL (e.g. after a bad auto-import scrape)."""

    def __init__(self, app_id: int, company: str, role: str, job_url: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.company = company
        self.role = role
        self.job_url = job_url

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Edit Application #{self.app_id}"),
            Label("Company"),
            Input(value=self.company, id="edit-company"),
            Label("Role"),
            Input(value=self.role, id="edit-role"),
            Label("Job URL (empty = clear)"),
            Input(value=self.job_url or "", id="edit-url"),
            Horizontal(
                Button("Save", id="save", variant="primary"),
                Button("Cancel", id="cancel"),
            ),
            id="edit-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss({
                "company": self.query_one("#edit-company", Input).value,
                "role": self.query_one("#edit-role", Input).value,
                "job_url": self.query_one("#edit-url", Input).value,
            })
        else:
            self.dismiss(None)
