import asyncio

import pytest
from textual.widgets import Input, Select, Button

from cv_optimizer.tui.app import CvDashboard
from cv_optimizer.tui.screens.modals import ConfirmModal


async def tab_to(pilot, app, widget_id):
    for _ in range(12):
        if app.focused is not None and app.focused.id == widget_id:
            assert 0 <= app.focused.region.y < app.focused.region.bottom <= app.size.height
            return
        await pilot.press("tab")
    raise AssertionError(f"Keyboard could not reach {widget_id}")


def test_edit_keyboard_and_live_resize(temp_db, temp_apps_dir):
    app_id = temp_db.insert_application("Original", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press("e")
            modal = app.screen
            company = modal.query_one("#edit-company", Input)
            await tab_to(pilot, app, "edit-company")
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
            await pilot.press("e")
            await tab_to(pilot, app, "cancel")
            await pilot.press("enter")
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
            await tab_to(pilot, app, select_id)
            await pilot.press("enter", "end")
            overlay = select.query_one("SelectOverlay")
            assert overlay.region.bottom <= 12 and overlay.region.y >= 0
            await pilot.press("enter")
            assert select.value == ("interview 1" if key == "s" else "mechanical_engineering")
            await pilot.press("escape")
            assert len(app.screen_stack) == 1
            assert temp_db.get_application_profile(app_id) == ("it", 0)
            assert temp_db.get_latest_status(app_id) == "draft"
            await pilot.press(key)
            await tab_to(pilot, app, "cancel")
            await pilot.press("enter")
            assert len(app.screen_stack) == 1
            await pilot.press(key)
            await tab_to(pilot, app, select_id)
            await pilot.press("enter", "end", "enter")
            await tab_to(pilot, app, "confirm")
            await pilot.press("enter")
            if key == "v":
                await tab_to(pilot, app, "yes")
                await pilot.press("enter")
                assert temp_db.get_application_profile(app_id) == ("mechanical_engineering", 1)
            else:
                assert temp_db.get_latest_status(app_id) == "interview 1"

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
            await tab_to(pilot, app, "cancel")
            await pilot.press("enter")
            assert temp_db.list_applications_with_status()[0]["source"] == "referral"
            await pilot.press("T")
            await tab_to(pilot, app, "clear")
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
            await tab_to(pilot, app, "no")
            assert no.region.bottom <= 12
            await pilot.press("enter")
            assert outcomes == [False]

    asyncio.run(run())
