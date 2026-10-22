import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from textual.widgets import DataTable, Input, Static

from cv_optimizer.tui.app import CvDashboard


@pytest.mark.parametrize("operation", ["cv", "cover_letter"])
def test_generation_completes_behind_live_edit(temp_db, temp_apps_dir, tmp_path, monkeypatch, operation):
    jd = tmp_path / "jd.txt"
    jd.write_text("Synthetic vacancy")
    first = temp_db.insert_application("A", "Engineer", cv_profile="it", jd_path=str(jd))
    second = temp_db.insert_application("B", "Engineer", cv_profile="it")
    started, release = threading.Event(), threading.Event()
    document = tmp_path / "generated.pdf"
    column = "cv_path" if operation == "cv" else "cover_letter_path"
    completed = "CV regenerated" if operation == "cv" else "Cover letter generated"
    unsaved = "Unsaved B [literal] 界 " + "Long company name " * 8

    def generate(app_id, **kwargs):
        started.set()
        assert release.wait(15), "fake worker was not released"
        document.write_bytes(b"synthetic")
        with temp_db.connect() as conn:
            conn.execute(f"UPDATE applications SET {column} = ? WHERE id = ?", (str(document), app_id))

    service = Mock(side_effect=generate)
    monkeypatch.setattr("cv_optimizer.tui.app." + ("reoptimize" if operation == "cv" else "generate_cover_letter"), service)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(160, 50)) as pilot:
            table = app.query_one(DataTable)
            app.refresh_apps(select_id=first)
            await pilot.press("ctrl+r" if operation == "cv" else "ctrl+g")
            app.screen.query_one("#yes").focus()
            await pilot.press("enter")
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.01)
            assert started.is_set()
            app.refresh_apps(select_id=second)
            app.dashboard.query_one("#filter-input", Input).value = "Engineer"
            await pilot.press("e")
            modal = app.screen
            field = modal.query_one("#edit-company", Input)
            field.value = unsaved
            field.focus()
            for size in [(40, 12), (80, 24), (120, 18), (160, 12), (39, 12), (40, 11), (40, 12)]:
                await pilot.resize_terminal(*size)
            assert ("Regenerating CV" if operation == "cv" else "Generating cover letter") in app.operation_message
            service.assert_called_once()
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.screen is modal and field.value == unsaved
            assert app.focused is field
            assert app._selected_app()["id"] == second
            assert app.filter_text == "Engineer"
            assert next(a for a in app.applications if a["id"] == first)[column] == str(document)
            assert completed in app.latest_message
            service.assert_called_once()
            await pilot.resize_terminal(160, 12)
            await pilot.pause()
            assert "✓" in table.get_cell(str(first), "Docs")
            assert app.screen is modal and field.value == unsaved
            await pilot.resize_terminal(40, 12)
            for _ in range(6):
                if app.focused.id == "save":
                    break
                await pilot.press("tab")
            assert app.focused.id == "save" and app.focused.region.bottom <= 12
            await pilot.press("enter")
            records = {a["id"]: a for a in temp_db.list_applications_with_status()}
            assert records[second]["company"] == unsaved.strip()
            assert records[first]["company"] == "A"
            assert records[first][column] == str(document)
            assert app._selected_app()["id"] == second
            app.action_operation_status()
            await pilot.pause()
            assert "Updated" in str(app.screen.query_one("#text-content", Static).render())

    try:
        asyncio.run(run())
    finally:
        release.set()


def test_error_survives_refresh_resize_and_status_view(temp_db, tmp_path, monkeypatch):
    jd = tmp_path / "jd.txt"
    jd.write_text("synthetic")
    temp_db.insert_application("Company", "Engineer", jd_path=str(jd))
    error = "Synthetic worker error " * 30
    service = Mock(side_effect=RuntimeError(error))
    monkeypatch.setattr("cv_optimizer.matching.MatchService.score_application", service)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press("m")
            await app.workers.wait_for_complete()
            service.assert_called_once()
            app.action_refresh()
            await pilot.resize_terminal(160, 50)
            app.action_operation_status()
            await pilot.pause()
            assert error in str(app.screen.query_one("#text-content", Static).render())

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["score", "discovery"])
def test_operation_finishes_with_details_open(temp_db, tmp_path, monkeypatch, operation):
    from cv_optimizer.config import settings

    jd = tmp_path / "jd.txt"
    jd.write_text("synthetic")
    app_id = temp_db.insert_application("Company", "Engineer", jd_path=str(jd))
    started, release = threading.Event(), threading.Event()

    def finish(*args, **kwargs):
        started.set()
        assert release.wait(15)
        temp_db.set_source(app_id, "Updated by fake worker")
        if operation == "score":
            return {"score": 85, "label": "Strong", "cached": False}
        return SimpleNamespace(imported=1)

    service = Mock(side_effect=finish)
    if operation == "score":
        monkeypatch.setattr("cv_optimizer.matching.MatchService.score_application", service)
    else:
        monkeypatch.setattr(settings, "enable_discovery", True)
        monkeypatch.setattr("cv_optimizer.discovery.config.load_config", Mock(return_value=None))
        monkeypatch.setattr("cv_optimizer.discovery.lock.DiscoveryLock", Mock(return_value=Mock(acquire=Mock(return_value=True))))
        monkeypatch.setattr("cv_optimizer.discovery.service.DiscoveryService", Mock(return_value=Mock(run=service)))

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(160, 50)) as pilot:
            if operation == "score":
                await pilot.press("m")
            else:
                app.action_discover_jobs()
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.01)
            assert started.is_set()
            await pilot.press("enter")
            screen = app.screen
            await pilot.resize_terminal(40, 12)
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.screen is screen
            assert "Updated by fake worker" in str(screen.query_one("#text-content", Static).render())
            service.assert_called_once()
            await pilot.press("escape")
            assert app._selected_app()["id"] == app_id

    try:
        asyncio.run(run())
    finally:
        release.set()


def test_scoring_shortcut_finishes_without_retargeting(temp_db, tmp_path, monkeypatch):
    jd = tmp_path / "jd.txt"
    jd.write_text("synthetic")
    first = temp_db.insert_application("Company A", "Engineer", jd_path=str(jd))
    second = temp_db.insert_application("Company B", "Engineer")
    score = Mock(return_value={"score": 85, "label": "Strong", "cached": False})
    monkeypatch.setattr("cv_optimizer.matching.MatchService.score_application", score)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            app.refresh_apps(select_id=first)
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            score.assert_called_once_with(first)
            assert "85 Strong" in app.latest_message
            app.refresh_apps(select_id=second)
            await pilot.press("enter")
            app.refresh_apps()
            assert app._selected_app()["id"] == second

    asyncio.run(run())
