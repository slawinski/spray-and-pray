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


def test_status_change_preserves_cursor_and_page(tmp_path, monkeypatch):
    """Regression: updating a status re-renders the table, which used to
    reset the page to 0 and drop the cursor onto the top row. The cursor
    must stay on the updated application's row, on the same page."""
    import cv_optimizer.db as db
    from cv_optimizer import tracker

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tui.db")
    monkeypatch.setattr(tracker, "APPLICATIONS_DIR", tmp_path / "apps")
    db.init_db()

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

            # Cursor on row 2 of page 2 (rows 20..24).
            app.current_page = 1
            app.render_table()
            table = app.query_one("#apps-table", DataTable)
            table.move_cursor(row=2)
            target_id = app.filtered[22]["id"]

            # Drive the real status-change flow (modal confirms current value;
            # update_status is a no-op but the refresh still runs).
            app.action_change_status()
            await pilot.pause()
            await pilot.click("#confirm")
            await pilot.pause()

            assert app.current_page == 1, "status update must not reset the page"
            assert table.cursor_row == 2, "cursor must stay on the updated row"
            selected = app._selected_app()
            assert selected is not None
            assert selected["id"] == target_id, (
                f"expected selected id {target_id}, got {selected['id']}"
            )

    asyncio.run(run())


def test_refresh_preserves_active_filter(tmp_path, monkeypatch):
    """refresh_apps(select_id=...) must re-apply the active filter text so
    the page computation and rendered list stay consistent."""
    import cv_optimizer.db as db
    from cv_optimizer import tracker

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tui.db")
    monkeypatch.setattr(tracker, "APPLICATIONS_DIR", tmp_path / "apps")
    db.init_db()

    for i in range(1, 6):
        app_id = db.insert_application(f"AlphaCo {i}", "Engineer")
        db.insert_status(app_id, "draft")
    db.insert_application("BetaCorp", "Engineer")

    async def run():
        from cv_optimizer.tui.app import CvDashboard

        app = CvDashboard()
        async with app.run_test(size=(120, 40)) as pilot:
            app.refresh_apps()
            assert len(app.filtered) == 6

            # Filter down to AlphaCo only.
            app.filter_text = "alphaco"
            app._apply_filter()
            assert len(app.filtered) == 5

            # A refresh with select_id must keep the filter applied.
            target_id = app.filtered[0]["id"]
            app.refresh_apps(select_id=target_id)
            assert len(app.filtered) == 5, "filter must survive refresh_apps"
            assert all("alphaco" in a["company"].lower() for a in app.filtered)
            assert app._selected_app() is not None
            assert app._selected_app()["id"] == target_id
            await pilot.pause()

    asyncio.run(run())
