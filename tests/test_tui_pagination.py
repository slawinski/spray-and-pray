"""Continuous browsing retains the former wrong-record regression coverage."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_selected_app_beyond_twentieth_row(tmp_path, monkeypatch):
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

            table = app.query_one("#apps-table", DataTable)
            assert table.row_count == 25
            table.move_cursor(row=20)

            selected = app._selected_app()
            assert selected is not None
            assert selected == app.filtered[20], (
                f"expected filtered[20] (id {app.filtered[20]['id']}), "
                f"got id {selected['id']}"
            )
            assert selected != app.filtered[0]

            table.move_cursor(row=23)
            assert app._selected_app() == app.filtered[23]

            table.move_cursor(row=2)
            assert app._selected_app() == app.filtered[2]
            await pilot.pause()

    asyncio.run(run())


def test_status_change_preserves_deep_cursor(tmp_path, monkeypatch):
    """Updating a status must not drop a deep cursor onto the first record."""
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

            table = app.query_one("#apps-table", DataTable)
            table.move_cursor(row=22)
            target_id = app.filtered[22]["id"]

            # Drive the real status-change flow (modal confirms current value;
            # update_status is a no-op but the refresh still runs).
            app.action_change_status()
            await pilot.pause()
            await pilot.click("#confirm")
            await pilot.pause()

            assert table.cursor_row == 22, "cursor must stay on the updated row"
            selected = app._selected_app()
            assert selected is not None
            assert selected["id"] == target_id, (
                f"expected selected id {target_id}, got {selected['id']}"
            )

    asyncio.run(run())


def test_refresh_preserves_active_filter(tmp_path, monkeypatch):
    """Refresh must re-apply active filter text and retain the selected ID."""
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
