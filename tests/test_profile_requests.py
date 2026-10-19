"""Request boundaries use synthetic records and never run paid generation."""

import asyncio
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

import server
from cv_optimizer import tracker


@pytest.mark.parametrize("fields", [{}, {"cv_profile": None}, {"cv_profile": ""}, {"cv_profile": "unknown"}])
def test_track_request_requires_explicit_profile(fields):
    with pytest.raises(ValidationError, match="cv_profile"):
        server.TrackRequest(company="Example", role="Engineer", jd="Synthetic vacancy", **fields)


@pytest.mark.parametrize("profile", ["it", "mechanical_engineering"])
def test_request_background_runner_tracker_propagation(temp_db, monkeypatch, profile):
    tracked = Mock(return_value=123)
    monkeypatch.setattr(tracker, "track", tracked)
    monkeypatch.setattr(server.os, "system", Mock())
    monkeypatch.setattr(server, "send_discord_notification", Mock())
    tasks = BackgroundTasks()
    request = server.TrackRequest(company="Example", role="Engineer", jd="Synthetic vacancy",
                                  url="https://example.com/job", source="referral", cv_profile=profile)
    result = asyncio.run(server.track_application(request, tasks))
    assert result["status"] == "success"
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].kwargs == {"cv_profile": profile}
    tracked.assert_not_called()
    asyncio.run(tasks())
    assert tracked.call_args.args[:2] == ("Example", "Engineer")
    assert tracked.call_args.kwargs == {
        "job_url": request.url, "source": "referral", "with_cover_letter": True, "cv_profile": profile,
    }


def test_later_letter_rejects_unselected_before_scheduling(temp_db, tmp_path):
    jd = tmp_path / "vacancy.txt"
    jd.write_text("Synthetic vacancy")
    app_id = temp_db.insert_application("Imported", "Engineer", jd_path=str(jd))
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        asyncio.run(server.generate_cover_letter_endpoint(app_id, tasks))
    assert error.value.status_code == 400
    assert "select" in error.value.detail.lower() and "profile" in error.value.detail.lower()
    assert tasks.tasks == []


def test_later_letter_schedules_selected_application(temp_db, tmp_path):
    jd = tmp_path / "vacancy.txt"
    jd.write_text("Synthetic vacancy")
    app_id = temp_db.insert_application("Selected", "Engineer", jd_path=str(jd), cv_profile="it")
    tasks = BackgroundTasks()
    asyncio.run(server.generate_cover_letter_endpoint(app_id, tasks))
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args == (app_id,)


def test_popup_both_flows_require_and_send_shared_selection():
    """Exercise popup listeners without Chrome, API traffic, or npm packages."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the isolated popup-script smoke")
    script = r"""
    const assert = require('node:assert/strict');
    const fs = require('node:fs');
    const vm = require('node:vm');
    const elements = {};
    for (const id of ['status', 'cv-profile', 'm-company', 'm-role', 'm-jd',
                      'm-url', 'extract-btn', 'manual-btn']) {
        elements[id] = {value: '', focus() {}, addEventListener(_, handler) {this.click = handler;}};
    }
    elements['m-company'].value = 'Example';
    elements['m-role'].value = 'Engineer';
    elements['m-jd'].value = 'Synthetic vacancy';
    const requests = [];
    const context = {
        document: {getElementById: id => elements[id]},
        chrome: {
            tabs: {query: async () => [{id: 1, url: 'https://example.com/job'}]},
            scripting: {executeScript: async () => [{result: {
                company: 'Example', role: 'Engineer', jd: 'Synthetic vacancy',
            }}]},
        },
        fetch: async (_, options) => {
            requests.push(JSON.parse(options.body));
            return {ok: true};
        },
    };
    vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
    (async () => {
        for (const button of ['extract-btn', 'manual-btn']) {
            elements['cv-profile'].value = '';
            const before = requests.length;
            await elements[button].click();
            assert.equal(requests.length, before);
            assert.match(elements.status.textContent, /select a CV profile/);
            for (const profile of ['it', 'mechanical_engineering']) {
                elements['cv-profile'].value = profile;
                await elements[button].click();
                assert.equal(requests.at(-1).cv_profile, profile);
                assert.equal(elements[button].disabled, false);
            }
        }
        assert.equal(requests.length, 4);
        let finishExtraction;
        let extractionStarted;
        const started = new Promise(resolve => {extractionStarted = resolve;});
        context.chrome.scripting.executeScript = () => {
            extractionStarted();
            return new Promise(resolve => {finishExtraction = resolve;});
        };
        elements['cv-profile'].value = 'it';
        const pending = elements['extract-btn'].click();
        await started;
        elements['cv-profile'].value = 'mechanical_engineering';
        finishExtraction([{result: {company: 'Example', role: 'Engineer', jd: 'Synthetic vacancy'}}]);
        await pending;
        assert.equal(requests.at(-1).cv_profile, 'it');
    })().catch(error => {console.error(error); process.exitCode = 1;});
    """
    popup = Path(__file__).resolve().parent.parent / "extension" / "popup.js"
    subprocess.run([node, "-e", script, str(popup)], check=True, capture_output=True, text=True)
