import asyncio
from unittest.mock import Mock

from textual.widgets import OptionList
from cv_optimizer.tui.app import CvDashboard


def test_reports_action_is_global_and_read_only(monkeypatch):
    app = CvDashboard()
    opened, notified = Mock(), Mock()
    monkeypatch.setattr('cv_optimizer.tui.app.webbrowser.open', opened)
    monkeypatch.setattr(app, '_notify', notified)
    monkeypatch.setattr('cv_optimizer.db.init_db', lambda: (_ for _ in ()).throw(AssertionError('writer')))
    assert ('reports', '', 'Reports (server must be running)', False) in app.available_actions()
    app.action_reports()
    opened.assert_called_once_with('http://localhost:8000/reports')
    assert 'server' in notified.call_args.args[0].lower()
    assert any(b.key == 'S' and b.action == 'sankey' for b in app.BINDINGS)


def test_palette_opens_reports_with_no_selected_application(temp_db, monkeypatch):
    opened = Mock()
    monkeypatch.setattr('cv_optimizer.tui.app.webbrowser.open', opened)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press('?')
            options = app.screen.query_one(OptionList)
            assert not options.get_option('reports').disabled
            options.highlighted = next(i for i in range(options.option_count) if options.get_option_at_index(i).id == 'reports')
            await pilot.press('enter')
            await pilot.pause()
            opened.assert_called_once_with('http://localhost:8000/reports')
    asyncio.run(run())
