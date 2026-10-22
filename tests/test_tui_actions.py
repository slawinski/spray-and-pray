import asyncio

from textual.widgets import DataTable, Input, OptionList

from cv_optimizer.tui.app import CvDashboard


def test_actions_and_filter_at_minimum(temp_db):
    for i in range(30):
        temp_db.insert_application(f"Company {i}", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            table = app.query_one(DataTable)
            table.move_cursor(row=25)
            selected = app._selected_app()["id"]
            assert "/ Filter" in str(app.query_one("#shortcut-bar").render())
            await pilot.press("?")
            options = app.screen.query_one(OptionList)
            actions = {options.get_option_at_index(i).id for i in range(options.option_count)}
            assert {"edit_application", "change_status", "browser_sankey", "operation_status", "clear_filter"} <= actions
            await pilot.press("end")
            assert options.highlighted == options.option_count - 1
            await pilot.press("escape")
            assert app._selected_app()["id"] == selected
            for key, action in [("e", "edit_application"), ("s", "change_status")]:
                await pilot.press(key)
                assert app.screen.app_id == selected
                await pilot.press("escape", "?")
                options = app.screen.query_one(OptionList)
                options.highlighted = next(i for i in range(options.option_count)
                                           if options.get_option_at_index(i).id == action)
                await pilot.press("enter")
                assert app.screen.app_id == selected
                await pilot.press("escape")
            await pilot.press("/")
            field = app.query_one("#filter-input", Input)
            assert app.focused is field and field.region.height == 3
            await pilot.press("q", "s", "e", "/", "?")
            assert field.value == "qse/?"
            assert len(app.screen_stack) == 1
            await pilot.press("escape")
            assert app.focused is table and field.value == "qse/?"
            assert not app.query_one("#filter-bar").display
            app.action_clear_filter()
            await pilot.press("?")
            options = app.screen.query_one(OptionList)
            options.highlighted = next(i for i in range(options.option_count)
                                       if options.get_option_at_index(i).id == "edit_application")
            await pilot.press("enter")
            assert app.screen.app_id == app._selected_app()["id"]
            await pilot.press("escape")

    asyncio.run(run())


def test_empty_results_disable_selected_actions(temp_db):
    temp_db.insert_application("Company", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(40, 12)) as pilot:
            await pilot.press("/")
            field = app.query_one(Input)
            field.value = "no match"
            await pilot.press("enter", "?")
            assert app._selected_app() is None
            options = app.screen.query_one(OptionList)
            assert options.get_option("edit_application").disabled
            for action in ["refresh", "focus_filter", "sankey", "quit"]:
                assert not options.get_option(action).disabled
            await pilot.press("escape")
            assert "No application selected" in str(app.query_one("#inspector-content").render())

    asyncio.run(run())
