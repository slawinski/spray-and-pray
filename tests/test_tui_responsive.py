import asyncio
from unittest.mock import Mock

from textual.widgets import DataTable, Static

from cv_optimizer.tui.app import CvDashboard
from cv_optimizer.tui.screens.modals import ResizeGuard


def seed(db, count=75):
    for i in range(count):
        app_id = db.insert_application(f"Company [bold] 界 e\u0301 {i} " + "Long identity " * 5,
                                       f"Role {i} " + "Engineering " * 6)
        db.insert_status(app_id, "draft")


def test_live_resize_selection_details_and_no_queries(temp_db, monkeypatch):
    seed(temp_db)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(160, 50)) as pilot:
            table = app.query_one(DataTable)
            app.filter_text = "company"
            app._apply_filter()
            table.move_cursor(row=57)
            await pilot.pause()
            selected = app._selected_app()
            assert table.size.height > 20
            assert app.query_one("#inspector").display
            assert selected["company"] in str(app.query_one("#inspector-content", Static).render())
            queries = Mock(side_effect=AssertionError("resize queried database"))
            for name in ("list_applications_with_status", "get_latest_matches", "get_latest_readiness_batch",
                         "get_job_posting_by_application"):
                monkeypatch.setattr(temp_db, name, queries)
            for width, height in [(40, 12), (60, 15), (79, 24), (80, 24), (119, 24),
                                  (120, 18), (160, 12), (120, 17), (160, 50)]:
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                assert app._selected_app()["id"] == selected["id"]
                assert app.filter_text == "company"
                assert app.focused is table
                assert table.scroll_y > 0
                assert table.max_scroll_x == 0, (width, height, app.size, table.size, app.mode, app._schema)
                assert app.query_one("#inspector").display == (width >= 120 and height >= 18)
                if width < 80:
                    row = table.get_row(str(selected["id"]))
                    assert len(row) == 1 and len(row[0].plain.splitlines()) == 3
                    assert "draft" in row[0].plain and "Match" in row[0].plain
            await pilot.resize_terminal(40, 12)
            await pilot.press("enter")
            content = str(app.screen.query_one("#text-content", Static).render())
            for value in (selected["company"], selected["role"], "CV profile:", "Source:", "Created:",
                          "Readiness:", "Match:", "JD:", "CV:", "CL:", "Status History:"):
                assert value in content
            await pilot.press("end")
            assert app.screen.query_one("#text-scroll").scroll_y > 0
            screen = app.screen
            for size in [(39, 12), (40, 11)]:
                await pilot.resize_terminal(*size)
                await pilot.press("escape", "s", "D")
                assert app.screen is screen
                assert screen.query_one(ResizeGuard).display
            await pilot.resize_terminal(40, 12)
            await pilot.press("escape")
            assert app._selected_app()["id"] == selected["id"]
            queries.assert_not_called()

    asyncio.run(run())
