"""TUI pagination regression: row actions must resolve the application
under the cursor on the CURRENT page, not index 0 of the filtered list."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_selected_app_respects_pagination(tmp_path, monkeypatch):
    import cv_optimizer.db as db
    from cv_optimizer import tracker

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tui.db")
    monkeypatch.setattr(tracker, "APPLICATIONS_DIR", tmp_path / "apps")
    db.init_db()

    # 25 applications with deterministic DESC ordering (id 25 newest).
    for i in range(1, 26):
        app_id = db.insert_application(f"Company {i}", "Frontend Engineer")
        db.insert_status(app_id, "draft")
        conn = db.connect()
        conn.execute(
            "UPDATE applications SET created_at = datetime('now', ?) WHERE id = ?",
            (f"+{i} seconds", app_id),
        )
        conn.close()

    async def run():
        from textual.widgets import DataTable

        from cv_optimizer.tui.app import CvDashboard

        app = CvDashboard()
        async with app.run_test(size=(120, 40)) as pilot:
            app.refresh_apps()
            assert len(app.filtered) == 25

            # Page 2 (rows 20..24). The old bug would resolve cursor row 0
            # to filtered[0] — the wrong application entirely.
            app.current_page = 1
            app.render_table()
            table = app.query_one("#apps-table", DataTable)
            table.move_cursor(row=0)

            selected = app._selected_app()
            assert selected is not None
            assert selected == app.filtered[20], (
                f"expected filtered[20] (id {app.filtered[20]['id']}), "
                f"got id {selected['id']}"
            )
            assert selected != app.filtered[0]

            table.move_cursor(row=3)
            assert app._selected_app() == app.filtered[23]

            # Page 1 behaves as before.
            app.current_page = 0
            app.render_table()
            table.move_cursor(row=2)
            assert app._selected_app() == app.filtered[2]
            await pilot.pause()

    asyncio.run(run())
