import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from textual.widgets import DataTable, Input, Static
from textual.worker import WorkerState

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
            document_column = "CV" if operation == "cv" else "CL"
            assert "✓" in table.get_cell(str(first), document_column)
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
    started, release = threading.Event(), threading.Event()

    def finish(app_id):
        started.set()
        assert release.wait(15)
        return {"score": 85, "label": "Strong", "cached": False}

    score = Mock(side_effect=finish)
    monkeypatch.setattr("cv_optimizer.matching.MatchService.score_application", score)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            app.refresh_apps(select_id=first)
            await pilot.press("m")
            await wait_until(started.is_set)
            table = app.query_one(DataTable)
            table.move_cursor(row=table.get_row_index(str(second)))
            await pilot.pause()
            await pilot.press("enter")
            details = app.screen
            assert "Company B" in str(details.query_one("#text-content", Static).render())
            await pilot.resize_terminal(160, 50)
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            score.assert_called_once_with(first)
            assert "Company A — Engineer: 85 Strong" in app.latest_message
            assert app.screen is details
            assert "Company B" in str(details.query_one("#text-content", Static).render())
            assert app._selected_app()["id"] == second

    try:
        asyncio.run(run())
    finally:
        release.set()


async def wait_until(predicate):
    for _ in range(300):
        if predicate():
            return
        await asyncio.sleep(.01)
    assert predicate(), "fake worker did not reach expected state"


@pytest.mark.parametrize("scoring", ["single", "bulk"])
@pytest.mark.parametrize("document", ["cv", "cover_letter"])
@pytest.mark.parametrize("first_done", ["scoring", "document"])
def test_overlapping_workers_keep_remaining_progress(temp_db, tmp_path, monkeypatch,
                                                     scoring, document, first_done):
    jd = tmp_path / "jd.txt"
    jd.write_text("synthetic")
    app_id = temp_db.insert_application("Company A", "Engineer", cv_profile="it", jd_path=str(jd))
    started = {name: threading.Event() for name in ("scoring", "document")}
    release = {name: threading.Event() for name in started}
    matches = {}
    monkeypatch.setattr(temp_db, "get_latest_matches", lambda ids: {i: matches[i] for i in ids if i in matches})

    def score(*args, **kwargs):
        if scoring == "bulk":
            kwargs["progress"]("Scoring fake batch 1/1")
        started["scoring"].set()
        assert release["scoring"].wait(15)
        matches[app_id] = {"score": 85, "label": "Strong", "confidence": "high", "assessment_json": "{}"}
        if scoring == "bulk":
            return {"scored": 1, "skipped_no_jd": 0, "errors": []}
        return {"score": 85, "label": "Strong", "cached": False}

    def generate(*args, **kwargs):
        started["document"].set()
        assert release["document"].wait(15)

    score_service, document_service = Mock(side_effect=score), Mock(side_effect=generate)
    monkeypatch.setattr("cv_optimizer.matching.MatchService." + (
        "score_application" if scoring == "single" else "score_missing_applications"), score_service)
    monkeypatch.setattr("cv_optimizer.tui.app." + (
        "reoptimize" if document == "cv" else "generate_cover_letter"), document_service)
    progress = {"scoring": "Scoring selected application" if scoring == "single" else "Scoring fake batch 1/1",
                "document": "Regenerating CV" if document == "cv" else "Generating cover letter"}
    completion = {"scoring": "Company A — Engineer: 85 Strong" if scoring == "single" else "Scored 1 application(s)",
                  "document": "CV regenerated" if document == "cv" else "Cover letter generated"}

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("m" if scoring == "single" else "M")
            await wait_until(started["scoring"].is_set)
            await pilot.press("ctrl+r" if document == "cv" else "ctrl+g")
            app.screen.query_one("#yes").focus()
            await pilot.press("enter")
            await wait_until(started["document"].is_set)
            app.action_operation_status()
            await pilot.pause()
            screen = app.screen
            content = lambda: str(screen.query_one("#text-content", Static).render())
            assert all(message in content() for message in progress.values())
            workers = {worker.group: worker for worker in app.workers}
            assert set(workers) == {"scoring", "default"}
            assert all(worker.state == WorkerState.RUNNING for worker in workers.values())
            await pilot.resize_terminal(40, 12)
            release[first_done].set()
            await wait_until(lambda: completion[first_done] in app.latest_message)
            await pilot.pause()
            remaining = "document" if first_done == "scoring" else "scoring"
            assert app.screen is screen
            assert progress[remaining] in content().split("Latest completion / error")[0]
            assert "No operation in progress" not in content()
            assert progress[remaining] in str(app.dashboard.query_one("#status-bar", Static).render())
            assert not release[remaining].is_set()
            assert workers["default" if remaining == "document" else "scoring"].state == WorkerState.RUNNING
            await pilot.resize_terminal(160, 50)
            release[remaining].set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "No operation in progress." in content()
            assert completion[remaining] in content()
            assert not app.operation_message
            assert app.matches[app_id]["score"] == 85
            assert not app.regenerating_ids and not app.generating_cl_ids
            assert score_service.call_count == document_service.call_count == 1
            if scoring == "single":
                score_service.assert_called_once_with(app_id)
            else:
                assert callable(score_service.call_args.kwargs["progress"])

    try:
        asyncio.run(run())
    finally:
        for event in release.values():
            event.set()
