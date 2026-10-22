import asyncio
from unittest.mock import Mock

from textual.widgets import DataTable, Input

from cv_optimizer.tui.app import CvDashboard


def test_batches_cache_and_failed_refresh(temp_db, monkeypatch):
    records = [dict(id=i, company=f"Company {i}", role="Engineer", created_at="",
                    latest_status="draft", history=[], jd_path=None, cv_path=None)
               for i in range(1001)]
    load = Mock(return_value=records)
    matches = Mock(side_effect=lambda ids: {i: {"score": i % 100, "label": "Match",
                                               "confidence": "high", "assessment_json": "{}"} for i in ids})
    readiness = Mock(return_value={})
    monkeypatch.setattr(temp_db, "list_applications_with_status", load)
    monkeypatch.setattr(temp_db, "get_latest_matches", matches)
    monkeypatch.setattr(temp_db, "get_latest_readiness_batch", readiness)

    async def run():
        app = CvDashboard()
        async with app.run_test() as pilot:
            table = app.query_one(DataTable)
            assert table.row_count == 1001
            assert [len(c.args[0]) for c in matches.call_args_list] == [500, 500, 1]
            table.move_cursor(row=57)
            target = app._selected_app()["id"]
            assert "57" in table.get_cell(str(target), "Match")
            assert app.matches[1000]["score"] == 0
            app.render_table()
            app.query_one(Input).value = "Company"
            await pilot.pause()
            assert app._selected_app()["id"] == target
            assert load.call_count == 1 and matches.call_count == 3
            load.side_effect = RuntimeError("synthetic refresh failure")
            app.refresh_apps()
            assert table.row_count == 1001
            assert app._selected_app()["id"] == target
            assert "synthetic refresh failure" in str(app.query_one("#status-bar").render())
            app.query_one(Input).value = "no results"
            await pilot.pause()
            assert app._selected_app() is None
            app.action_change_status()
            assert len(app.screen_stack) == 1

    asyncio.run(run())


def test_deleted_selection_uses_neighbor(temp_db):
    for i in range(4):
        temp_db.insert_application(f"Company {i}", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test() as pilot:
            table = app.query_one(DataTable)
            table.move_cursor(row=2)
            next_id = app.filtered[3]["id"]
            with temp_db.connect() as conn:
                conn.execute("DELETE FROM applications WHERE id = ?", (app._selected_app()["id"],))
            app.refresh_apps()
            assert app._selected_app()["id"] == next_id
            with temp_db.connect() as conn:
                conn.execute("DELETE FROM applications WHERE id = ?", (next_id,))
            app.refresh_apps()
            assert table.cursor_row == 1
            with temp_db.connect() as conn:
                conn.execute("DELETE FROM applications")
            app.refresh_apps()
            assert app._selected_app() is None
            await pilot.pause()

    asyncio.run(run())
