from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class StatusModal(ModalScreen[str]):
    def __init__(self, app_id: int, current_status: str) -> None:
        super().__init__()
        self.app_id = app_id
        self.current_status = current_status

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Change status for Application #{self.app_id}"),
            Input(value=self.current_status, placeholder="Enter new status", id="status-input"),
            Horizontal(
                Button("Confirm", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ),
            id="status-modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            status_input = self.query_one("#status-input", Input)
            self.dismiss(status_input.value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


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
