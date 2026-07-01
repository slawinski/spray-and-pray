import re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from cv_optimizer import db

BASE_STATUSES = ["applied", "ghosted", "rejected", "offer", "accepted"]


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
