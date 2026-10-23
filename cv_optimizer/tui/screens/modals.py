import re
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, OptionList
from textual.widgets.option_list import Option

from cv_optimizer import db

BASE_STATUSES = ["draft", "applied", "ghosted", "withdrawn", "rejected", "offer", "accepted"]
PROFILE_LABELS = {"it": "IT", "mechanical_engineering": "Mechanical Engineering"}


class ResizeGuard(Static, can_focus=True):
    DEFAULT_CSS = """
    ResizeGuard {
        display: none; layer: overlay; dock: top; width: 100%; height: 100%;
        background: $background; content-align: center middle;
    }
    """
    previous_focus = None

    def __init__(self):
        super().__init__("Resize to at least 40 × 12\nq Quit", markup=False)

    def on_key(self, event) -> None:
        event.stop()
        event.prevent_default()
        if event.key == "q":
            self.app.exit()


class TextScreen(ModalScreen[None]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, title: str, content: str | Text, *, application_id: int | None = None):
        super().__init__()
        self.title_text, self.content_text = title, content
        self.application_id = application_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="text-screen"):
            yield Label(self.title_text, markup=False)
            with ScrollableContainer(id="text-scroll"):
                yield Static(self.content_text, id="text-content", markup=False)
            yield Label("↑↓ Scroll · Esc Close")
        yield ResizeGuard()

    def on_mount(self) -> None:
        self.query_one("#text-scroll").focus()
        self.app._size_guard(self)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ActionsScreen(ModalScreen[str]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, commands, has_selection):
        super().__init__()
        self.commands, self.has_selection = commands, has_selection

    def compose(self) -> ComposeResult:
        with Vertical(classes="text-screen"):
            yield Label("Actions · Esc Close")
            yield OptionList(*(Option(f"{key or '·'}  {label}" + (" · selected" if required else ""),
                                      id=action, disabled=required and not self.has_selection)
                               for action, key, label, required in self.commands), id="actions-list")
        yield ResizeGuard()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()
        self.app._size_guard(self)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


def dialog(body, actions, *, id):
    return Vertical(ScrollableContainer(*body, classes="dialog-body"),
                    Horizontal(*actions, classes="dialog-actions"), id=id, classes="dialog")


class ResponsiveModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def on_mount(self) -> None:
        self.reflow()

    def on_resize(self) -> None:
        self.call_after_refresh(self.reflow)

    def reflow(self) -> None:
        spacious = self.app.size.width >= 50 and self.app.size.height >= 24
        self.set_class(spacious, "spacious")
        frame = self.query_one(".dialog")
        padding = (1 if frame.id == "profile-modal" else 2) if spacious else 0
        frame.styles.padding = (padding, 2 if spacious else 1)
        frame.styles.height = "auto"
        body = frame.query_one(".dialog-body")
        body.styles.height = "auto"
        body.styles.max_height = max(1, self.app.size.height - 2 - padding * 2 - 3 - int(spacious))
        for overlay in self.query("SelectOverlay"):
            overlay.styles.max_height = max(3, min(8, self.app.size.height - 4))
        self.app._size_guard(self)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProfileModal(ResponsiveModal):
    """None is cancellation; a blank selection cannot be confirmed."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, app_id: int, current_profile: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.current_profile = current_profile

    def compose(self) -> ComposeResult:
        yield dialog([
            Label(f"CV profile for Application #{self.app_id}"),
            Select([(label, name) for name, label in PROFILE_LABELS.items()],
                   id="profile-select", prompt="Select a profile...",
                   value=self.current_profile if self.current_profile else Select.NULL),
            ], [
                Button("Confirm", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ],
            id="profile-modal",
        )
        yield ResizeGuard()

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


class StatusModal(ResponsiveModal):
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

        yield dialog([
            Label(f"Change status for Application #{self.app_id}"),
            Select(options, id="status-select", prompt="Select new status...", value=self.current_status),
            ], [
                Button("Confirm", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ],
            id="status-modal",
        )
        yield ResizeGuard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            select = self.query_one("#status-select", Select)
            if not select.is_blank():
                self.dismiss(select.value)
        else:
            self.dismiss(None)

    def on_select_changed(self, event: Select.Changed) -> None:
        self.current_status = str(event.value) if event.value else self.current_status


class SankeyScreen(TextScreen):
    def __init__(self):
        from cv_optimizer.sankey import build_sankey_flows, render_sankey

        flows = build_sankey_flows(db.get_all_transitions())
        super().__init__("Application funnel", render_sankey(flows, compact=True))


class ConfirmModal(ResponsiveModal):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.modal_title = title
        self.modal_message = message

    def compose(self) -> ComposeResult:
        yield dialog([
            Label(self.modal_title, id="confirm-title", markup=False),
            Label(self.modal_message, id="confirm-message", markup=False),
            ], [
                Button("Yes", id="yes", variant="primary"),
                Button("No", id="no"),
            ],
            id="confirm-modal",
        )
        yield ResizeGuard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class SourceModal(ResponsiveModal):
    """Lets the user override the JD source for an application."""

    def __init__(self, app_id: int, company: str, current_source: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.company = company
        self.current_source = current_source

    def compose(self) -> ComposeResult:
        current_label = f"Current: {self.current_source}" if self.current_source else "Current: auto-detect"
        yield dialog([
            Label(f"Set source for {self.company} (App #{self.app_id})", markup=False),
            Label(current_label, id="current-source", markup=False),
            Horizontal(
                Button("Referral", id="referral", variant="primary"),
                Button("Recruiter", id="recruiter", variant="primary"),
            ),
            ], [
                Button("Clear (auto-detect)", id="clear"),
                Button("Cancel", id="cancel"),
            ],
            id="confirm-modal",
        )
        yield ResizeGuard()

    def action_cancel(self) -> None:
        self.dismiss(self.current_source)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "referral":
            self.dismiss("referral")
        elif event.button.id == "recruiter":
            self.dismiss("recruiter")
        elif event.button.id == "clear":
            self.dismiss(None)
        else:
            self.dismiss(self.current_source)  # cancel — keep current


class EditModal(ResponsiveModal):
    """Corrects company/role/job URL (e.g. after a bad auto-import scrape)."""

    def __init__(self, app_id: int, company: str, role: str, job_url: str | None) -> None:
        super().__init__()
        self.app_id = app_id
        self.company = company
        self.role = role
        self.job_url = job_url

    def compose(self) -> ComposeResult:
        yield dialog([
            Label(f"Edit Application #{self.app_id}"),
            Label("Company"),
            Input(value=self.company, id="edit-company"),
            Label("Role"),
            Input(value=self.role, id="edit-role"),
            Label("Job URL (empty = clear)"),
            Input(value=self.job_url or "", id="edit-url"),
            ], [
                Button("Save", id="save", variant="primary"),
                Button("Cancel", id="cancel"),
            ],
            id="edit-modal",
        )
        yield ResizeGuard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss({
                "company": self.query_one("#edit-company", Input).value,
                "role": self.query_one("#edit-role", Input).value,
                "job_url": self.query_one("#edit-url", Input).value,
            })
        else:
            self.dismiss(None)
