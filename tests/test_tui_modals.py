import asyncio

import pytest
from textual.widgets import Input, Select, Button

from cv_optimizer.tui.app import CvDashboard
from cv_optimizer.tui.screens.modals import ConfirmModal


def test_edit_keyboard_and_live_resize(temp_db, temp_apps_dir):
    app_id = temp_db.insert_application("Original", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press("e")
            modal = app.screen
            company = modal.query_one("#edit-company", Input)
            company.focus()
            await pilot.press("home", "shift+end")
            await pilot.press("q", "s", "e", "/", "?")
            assert company.value == "qse/?"
            await pilot.resize_terminal(160, 50)
            await pilot.resize_terminal(39, 12)
            await pilot.press("escape", "D")
            assert app.screen is modal
            await pilot.resize_terminal(40, 12)
            await pilot.pause()
            assert app.screen is modal and company.value == "qse/?"
            assert app.focused is company
            await pilot.press("tab")
            assert app.focused.id == "edit-role", [(w.id, w.region, w.display, w.visible) for w in modal.focus_chain]
            await pilot.press("home", "shift+end", "N", "e", "w")
            await pilot.press("tab")
            assert app.focused.id == "edit-url"
            await pilot.press("tab")
            assert app.focused.id == "save"
            assert app.focused.region.bottom <= 12
            await pilot.press("enter")
            record = next(a for a in temp_db.list_applications_with_status() if a["id"] == app_id)
            assert record["company"] == "qse/?" and record["role"] == "New"
            await pilot.press("e", "escape")
            assert len(app.screen_stack) == 1

    asyncio.run(run())


@pytest.mark.parametrize("key,select_id", [("s", "status-select"), ("v", "profile-select")])
def test_select_last_option_and_cancel_at_minimum(temp_db, key, select_id):
    app_id = temp_db.insert_application("Company", "Engineer", cv_profile="it")
    temp_db.insert_status(app_id, "draft")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press(key)
            select = app.screen.query_one(Select)
            select.focus()
            await pilot.press("enter", "end")
            overlay = select.query_one("SelectOverlay")
            assert overlay.region.bottom <= 12 and overlay.region.y >= 0
            await pilot.press("enter")
            assert select.value == ("interview 1" if key == "s" else "mechanical_engineering")
            await pilot.press("escape")
            assert len(app.screen_stack) == 1
            assert temp_db.get_application_profile(app_id) == ("it", 0)
            assert temp_db.get_latest_status(app_id) == "draft"

    asyncio.run(run())


def test_source_clear_cancel_and_long_confirmation(temp_db):
    app_id = temp_db.insert_application("Company", "Engineer")
    temp_db.set_source(app_id, "referral")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press("T", "escape")
            assert len(app.screen_stack) == 1
            assert temp_db.list_applications_with_status()[0]["source"] == "referral"
            await pilot.press("T")
            app.screen.query_one("#clear", Button).focus()
            await pilot.press("enter")
            assert temp_db.list_applications_with_status()[0]["source"] is None
            outcomes = []
            app.push_screen(ConfirmModal("Long confirmation", "Literal [bold] 界 " * 100), outcomes.append)
            await pilot.pause()
            body = app.screen.query_one(".dialog-body")
            body.focus()
            await pilot.press("end")
            assert body.scroll_y > 0
            no = app.screen.query_one("#no", Button)
            no.focus()
            assert no.region.bottom <= 12
            await pilot.press("enter")
            assert outcomes == [False]

    asyncio.run(run())
