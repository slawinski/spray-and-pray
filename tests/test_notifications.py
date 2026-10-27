"""External delivery is opt-in; no real webhook or desktop calls in these tests."""

import os
import subprocess
import sys
from unittest.mock import Mock

import pytest
import requests

import server
from cv_optimizer import tracker
from cv_optimizer.discovery import notify


@pytest.mark.parametrize("value,expected", [(None, False), ("false", False), ("true", True)])
def test_notification_setting(value, expected):
    env = os.environ.copy()
    env.pop("ENABLE_NOTIFICATIONS", None)
    if value is not None:
        env["ENABLE_NOTIFICATIONS"] = value
    result = subprocess.run(
        [sys.executable, "-c", "import dotenv; dotenv.load_dotenv = lambda: None; "
         "from cv_optimizer.config import settings; print(settings.enable_notifications)"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == str(expected)


@pytest.fixture
def delivery(monkeypatch):
    settings = server.settings
    monkeypatch.setattr(notify, "settings", settings)
    monkeypatch.setattr(settings, "discord_webhook_url", "https://example.invalid/webhook")
    http, desktop, discovery_desktop = Mock(), Mock(), Mock()
    monkeypatch.setattr(requests, "post", http)
    monkeypatch.setattr(server.os, "system", desktop)
    monkeypatch.setattr(subprocess, "run", discovery_desktop)
    return settings, http, desktop, discovery_desktop


@pytest.mark.parametrize("enabled", [False, True])
def test_completion_and_discovery_delivery(delivery, monkeypatch, enabled, caplog):
    settings, http, desktop, discovery_desktop = delivery
    monkeypatch.setattr(settings, "enable_notifications", enabled)
    server._notify_document_ready(title="Ready", description="Done", desktop_message="Done", color=0)
    with caplog.at_level("INFO"):
        notify.notify_new_imports([{"company": "Acme", "role": "Engineer", "score": 90}])
    assert http.call_count == (2 if enabled else 0)
    assert desktop.call_count == discovery_desktop.call_count == int(enabled)
    assert "1 new qualifying Drafts" in caplog.text


def test_enabled_without_webhook_still_delivers_desktop(delivery, monkeypatch):
    settings, http, desktop, discovery_desktop = delivery
    monkeypatch.setattr(settings, "enable_notifications", True)
    monkeypatch.setattr(settings, "discord_webhook_url", None)
    server._notify_document_ready(title="Ready", description="Done", desktop_message="Done", color=0)
    notify.notify_new_imports([{"company": "Acme", "role": "Engineer", "score": 90}])
    http.assert_not_called()
    assert desktop.call_count == discovery_desktop.call_count == 1


@pytest.mark.parametrize("later_letter", [False, True])
def test_generation_failures_are_silent_when_disabled(delivery, monkeypatch, later_letter, caplog):
    settings, http, desktop, discovery_desktop = delivery
    monkeypatch.setattr(settings, "enable_notifications", False)
    fail = Mock(side_effect=RuntimeError("generation failed"))
    if later_letter:
        monkeypatch.setattr(tracker, "generate_cover_letter", fail)
        server._run_cover_letter_generation(123)
    else:
        monkeypatch.setattr(tracker, "track", fail)
        server.run_cv_optimizer("Acme", "Engineer", "Job description", cv_profile="it")
    fail.assert_called_once()
    http.assert_not_called()
    desktop.assert_not_called()
    discovery_desktop.assert_not_called()
    assert "generation failed" in caplog.text
