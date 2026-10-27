"""Initial form focus and resize restoration against synthetic applications."""

import asyncio

import pytest
from textual.containers import Vertical
from textual.widgets import Button, Input, Select

from cv_optimizer.tui.app import CvDashboard
from cv_optimizer.tui.screens.modals import (
    ActionsScreen, ConfirmModal, EditModal, ProfileModal, ResizeGuard,
    ResponsiveModal, SourceModal, StatusModal, TextScreen, dialog,
)


@pytest.mark.parametrize("size", [(80, 24), (40, 12)])
@pytest.mark.parametrize("kind,field_id", [
    ("profile", "profile-select"), ("status", "status-select"), ("edit", "edit-company"),
])
def test_form_opens_ready_for_keyboard_input(temp_db, size, kind, field_id):
    app_id = temp_db.insert_application("Example", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            for _ in range(2):
                modal = {
                    "profile": lambda: ProfileModal(app_id, None),
                    "status": lambda: StatusModal(app_id, "draft"),
                    "edit": lambda: EditModal(app_id, "Example", "Engineer", None),
                }[kind]()
                await app.push_screen(modal)
                await pilot.pause()
                field = modal.query_one(f"#{field_id}")
                assert app.focused is field
                if isinstance(field, Select):
                    await pilot.press("enter")
                    assert field.expanded
                    await pilot.press("escape")
                else:
                    await pilot.press("end", "x")
                    assert field.value == "Examplex"
                    await pilot.press("tab")
                    role = modal.query_one("#edit-role")
                    assert app.focused is role
                    await pilot.resize_terminal(60, 18)
                    await pilot.pause()
                    assert app.focused is role
                    await pilot.resize_terminal(*size)
                await pilot.press("escape")
                assert app.screen is app.dashboard

    asyncio.run(run())


def test_guard_restores_initial_and_later_form_focus(temp_db):
    async def run():
        app = CvDashboard()
        async with app.run_test(size=(39, 11)) as pilot:
            modal = EditModal(1, "Example", "Engineer", None)
            await app.push_screen(modal)
            await pilot.pause()
            assert app.focused is modal.query_one(ResizeGuard)
            await pilot.resize_terminal(40, 12)
            await pilot.pause()
            assert app.focused is modal.query_one("#edit-company")
            await pilot.press("tab")
            role = modal.query_one("#edit-role")
            assert app.focused is role
            await pilot.resize_terminal(39, 11)
            await pilot.pause()
            assert app.focused is modal.query_one(ResizeGuard)
            await pilot.resize_terminal(80, 24)
            await pilot.pause()
            assert app.focused is role

    asyncio.run(run())


class ReadOnlyInput(Input):
    read_only = True


class UnavailableFieldsModal(ResponsiveModal):
    def compose(self):
        hidden = Vertical(Input(id="hidden"))
        hidden.display = False
        invisible = Input(id="invisible")
        invisible.visible = False
        yield dialog([
            hidden, invisible, Input(disabled=True), ReadOnlyInput(),
            Select([("IT", "it")], id="available"), Input(id="later"),
        ], [Button("Cancel")], id="fixture-modal")
        yield ResizeGuard()


def test_unavailable_fields_and_non_form_screens(temp_db):
    async def run():
        app = CvDashboard()
        async with app.run_test() as pilot:
            for modal, target in [
                (UnavailableFieldsModal(), "#available"),
                (ConfirmModal("Confirm", "Synthetic action"), ".dialog-body"),
                (SourceModal(1, "Example", None), ".dialog-body"),
                (TextScreen("Title", "Synthetic text"), "#text-scroll"),
                (ActionsScreen([("refresh", "r", "Refresh", False)], False), "#actions-list"),
            ]:
                await app.push_screen(modal)
                await pilot.pause()
                assert app.focused is modal.query_one(target)
                await pilot.press("escape")

    asyncio.run(run())
