"""Pilot exercises real selection controls against an isolated database."""

import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import DataTable, Select, Static

from cv_optimizer.tui.app import CvDashboard


async def choose(pilot, profile):
    await pilot.click("#profile-select")
    await pilot.press("home", "down")
    if profile == "mechanical_engineering":
        await pilot.press("down")
    await pilot.press("enter")
    await pilot.click("#confirm")
    await pilot.pause()


@pytest.mark.parametrize("action,worker", [("ctrl+r", "_regenerate"), ("ctrl+g", "_generate_cover_letter")])
def test_first_document_selection_cancel_and_continue(temp_db, tmp_path, monkeypatch, action, worker):
    jd = tmp_path / "vacancy.txt"
    jd.write_text("Synthetic vacancy")
    app_id = temp_db.insert_application("Imported", "Engineer", jd_path=str(jd))
    temp_db.insert_status(app_id, "draft")
    generation = Mock()
    monkeypatch.setattr(CvDashboard, worker, generation)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter")
            assert "Not selected" in str(app.screen.query_one("#text-content", Static).render())
            await pilot.press("escape")
            await pilot.press(action)
            assert app.screen.query_one("#profile-select", Select).is_blank()
            await pilot.click("#confirm")  # blank cannot confirm
            assert len(app.screen_stack) == 2
            await pilot.click("#cancel")
            assert temp_db.get_application_profile(app_id) == (None, 0)
            generation.assert_not_called()
            await pilot.press(action)
            await pilot.press("escape")
            assert temp_db.get_application_profile(app_id) == (None, 0)
            generation.assert_not_called()
            await pilot.press(action)
            await choose(pilot, "mechanical_engineering")
            assert temp_db.get_application_profile(app_id) == ("mechanical_engineering", 1)
            generation.assert_not_called()
            assert "Generate" in app.screen.modal_title or "generate" in app.screen.modal_title
            await pilot.click("#yes")
            generation.assert_called_once()
            assert generation.call_args.args[0]["cv_profile"] == "mechanical_engineering"
            # Subsequent requests inherit stored choice, no profile prompt.
            await pilot.press(action)
            assert list(app.screen.query("#profile-select").results()) == []
            await pilot.click("#no")
            assert generation.call_count == 1

    asyncio.run(run())


@pytest.mark.parametrize("size", [(80, 24), (40, 12)])
def test_profile_change_warning_invalidation_and_cursor(temp_db, tmp_path, size):
    cv = tmp_path / "cv.pdf"
    letter = tmp_path / "letter.pdf"
    cv.write_bytes(b"old CV")
    letter.write_bytes(b"old letter")
    for i in range(25):
        app_id = temp_db.insert_application(f"Example {i}", "Engineer", cv_profile="it",
                                            cv_path=str(cv))
        with temp_db.connect() as conn:
            conn.execute("UPDATE applications SET cover_letter_path = ? WHERE id = ?", (str(letter), app_id))
        temp_db.insert_status(app_id, "draft")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            table = app.query_one("#apps-table", DataTable)
            table.move_cursor(row=22)
            selected_id = app._selected_app()["id"]
            before = temp_db.get_application(selected_id)
            await pilot.press("v")
            await pilot.click("#cancel")
            assert temp_db.get_application(selected_id) == before
            await pilot.press("v")
            await pilot.click("#confirm")  # same choice: no warning, no mutation
            assert len(app.screen_stack) == 1
            assert temp_db.get_application_profile(selected_id) == ("it", 0)
            assert temp_db.get_application(selected_id) == before
            await pilot.press("v")
            await choose(pilot, "mechanical_engineering")
            assert "files" in app.screen.modal_message.lower()
            assert "regenerat" in app.screen.modal_message.lower()
            confirmation = app.screen
            await pilot.resize_terminal(160, 50)
            await pilot.resize_terminal(*size)
            assert app.screen is confirmation
            await pilot.click("#no")
            assert temp_db.get_application_profile(selected_id) == ("it", 0)
            await pilot.press("v")
            await choose(pilot, "mechanical_engineering")
            await pilot.click("#yes")
            await pilot.pause()
            assert table.cursor_row == 22
            selected = app._selected_app()
            assert selected["id"] == selected_id
            assert selected["cv_path"] is None and selected["cover_letter_path"] is None
            assert temp_db.get_application_profile(selected_id) == ("mechanical_engineering", 1)
            assert cv.read_bytes() == b"old CV" and letter.read_bytes() == b"old letter"
            assert temp_db.get_latest_status(selected_id) == "draft"
            await pilot.press("enter")
            assert "Mechanical Engineering" in str(app.screen.query_one("#text-content", Static).render())
            other = next(a for a in app.applications if a["id"] != selected_id)
            assert other["cv_profile"] == "it" and other["cv_path"] == str(cv)

    asyncio.run(run())
