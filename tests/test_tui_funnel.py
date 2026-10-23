import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import OptionList, Static

from cv_optimizer.tui.app import CvDashboard


@pytest.mark.parametrize("size", [(40, 12), (200, 40)])
def test_shift_s_opens_browser_sankey_without_a_terminal_modal(temp_db, monkeypatch, size):
    app_id = temp_db.insert_application("Company", "Engineer")
    browser = Mock()
    monkeypatch.setattr("cv_optimizer.sankey.generate_sankey_html", browser)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            await pilot.press("S")
            browser.assert_called_once_with()
            assert len(app.screen_stack) == 1
            assert app._selected_app()["id"] == app_id

    asyncio.run(run())


@pytest.mark.parametrize("populated", [False, True])
def test_terminal_funnel_and_browser_access(temp_db, monkeypatch, populated):
    app_id = temp_db.insert_application("Company", "Engineer")
    if populated:
        for i, status in enumerate(["draft", "applied"] + [f"interview {n}" for n in range(1, 16)] + ["offer"]):
            with temp_db.connect() as conn:
                conn.execute("INSERT INTO status_history (application_id, status, transitioned_at) VALUES (?, ?, ?)",
                             (app_id, status, f"2026-10-22T12:{i:02d}:00"))
    browser = Mock()
    monkeypatch.setattr("cv_optimizer.sankey.generate_sankey_html", browser)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            selected = app._selected_app()["id"]
            await pilot.press("?")
            options = app.screen.query_one(OptionList)
            options.highlighted = next(i for i in range(options.option_count)
                                       if options.get_option_at_index(i).id == "terminal_funnel")
            await pilot.press("enter")
            text = str(app.screen.query_one("#text-content", Static).render())
            if populated:
                assert "applied → interview 1: 1" in text
                assert "interview 15 → offer: 1" in text
                assert "Total applications: 1" in text
                await pilot.press("end")
                assert app.screen.query_one("#text-scroll").scroll_y > 0
            else:
                assert "No transitions to display" in text
            assert app.screen.query_one("#text-scroll").max_scroll_x == 0
            await pilot.press("escape")
            assert app._selected_app()["id"] == selected
            await pilot.press("S")
            browser.assert_called_once()

    asyncio.run(run())
