"""Feature-flag gating for automated job discovery (ENABLE_DISCOVERY).

Discovery is opt-in: the TUI [J] key, `cv-opt discover`, and the daily
launchd agent all stay silent unless ENABLE_DISCOVERY=true.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
    ],
)
def test_env_flag_parsing(monkeypatch, value, expected):
    from cv_optimizer.config import _env_flag

    monkeypatch.setenv("ENABLE_DISCOVERY", value)
    assert _env_flag("ENABLE_DISCOVERY") is expected


def test_env_flag_default_off(monkeypatch):
    from cv_optimizer.config import _env_flag

    monkeypatch.delenv("ENABLE_DISCOVERY", raising=False)
    assert _env_flag("ENABLE_DISCOVERY") is False


def test_cli_noops_when_disabled(monkeypatch, capsys):
    """`cv-opt discover` exits 0 with a notice — no config load, no run, no notifications."""
    from cv_optimizer.config import settings
    from cv_optimizer.discovery import cli

    monkeypatch.setattr(settings, "enable_discovery", False)
    assert cli.run_discovery([]) == 0
    assert "disabled" in capsys.readouterr().out.lower()


def test_tui_hides_discover_binding_and_guards_action(tmp_path, monkeypatch):
    """J key absent and the action no-ops with a notice when disabled."""
    import asyncio

    import cv_optimizer.db as db
    import cv_optimizer.tui.app as app_mod
    from cv_optimizer.config import settings

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "flag.db")
    monkeypatch.setattr(settings, "enable_discovery", False)
    db.init_db()

    # BINDINGS are built at import — reload under the patched flag.
    importlib.reload(app_mod)
    try:
        assert "discover_jobs" not in [b.action for b in app_mod.CvDashboard.BINDINGS]
        assert "discover_jobs" not in [a[0] for a in app_mod.CvDashboard().available_actions()]

        async def run():
            from textual.widgets import Static

            app = app_mod.CvDashboard()
            async with app.run_test(size=(120, 40)):
                app.action_discover_jobs()
                assert app.discovering is False
                status = str(app.query_one("#status-bar", Static).render())
                assert "disabled" in status.lower()

        asyncio.run(run())
    finally:
        # Restore the module to the ambient flag value for other tests.
        importlib.reload(app_mod)


def test_tui_shows_discover_binding_when_enabled(monkeypatch):
    import cv_optimizer.tui.app as app_mod
    from cv_optimizer.config import settings

    monkeypatch.setattr(settings, "enable_discovery", True)
    importlib.reload(app_mod)
    try:
        assert "discover_jobs" in [b.action for b in app_mod.CvDashboard.BINDINGS]
        assert "discover_jobs" in [a[0] for a in app_mod.CvDashboard().available_actions()]
    finally:
        importlib.reload(app_mod)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
