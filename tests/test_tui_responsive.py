import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import DataTable, Input, Static

from cv_optimizer.tui.app import CvDashboard
from cv_optimizer.tui.screens.modals import ResizeGuard


def seed(db, count=75):
    for i in range(count):
        app_id = db.insert_application(f"Company [bold] 界 e\u0301 {i} " + "Long identity " * 5,
                                       f"Role {i} " + "Engineering " * 6)
        db.insert_status(app_id, "draft")


@pytest.mark.parametrize("size", [(40, 12), (80, 24), (120, 24), (200, 50)])
def test_interview_round_numbers_are_visible_in_rendered_rows(temp_db, size):
    for round_number in (1, 12):
        app_id = temp_db.insert_application(f"Round {round_number}", "Engineer")
        temp_db.insert_status(app_id, "applied")
        temp_db.insert_status(app_id, f"interview {round_number}")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            rendered = "\n".join(table.render_line(y).text for y in range(table.size.height))
            prefix = "interview" if size[0] < 80 else "Int."
            for round_number in (1, 12):
                assert f"{prefix} {round_number}" in rendered
            assert table.max_scroll_x == 0

    asyncio.run(run())


@pytest.mark.parametrize("size", [(40, 12), (80, 24), (120, 24), (180, 24), (240, 50)])
def test_document_checks_and_added_date_remain_visible(temp_db, size):
    cv_only = temp_db.insert_application("CV ready", "Engineer", cv_path="cv.pdf")
    cl_only = temp_db.insert_application("Letter ready", "Engineer")
    with temp_db.connect() as conn:
        conn.execute("UPDATE applications SET cover_letter_path = ? WHERE id = ?", ("letter.pdf", cl_only))
        conn.execute("UPDATE applications SET created_at = ?", ("2026-10-20T12:34:56",))

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            if size[0] < 80:
                first = table.get_row(str(cv_only))[0].plain
                second = table.get_row(str(cl_only))[0].plain
                assert "CV ✓  CL —  Added 2026-10-20" in first
                assert "CV —  CL ✓  Added 2026-10-20" in second
            else:
                assert {"CV", "CL", "Added"} <= {str(key.value) for key in table.columns}
                for app_id, cv, cl in [(cv_only, "✓", "—"), (cl_only, "—", "✓")]:
                    assert cv in table.get_cell(str(app_id), "CV")
                    assert cl in table.get_cell(str(app_id), "CL")
                    assert table.get_cell(str(app_id), "Added") == "2026-10-20"
            assert table.max_scroll_x == 0
            app.regenerating_ids.add(cv_only)
            app.generating_cl_ids.add(cl_only)
            app.render_table()
            await pilot.pause()
            if size[0] < 80:
                assert "CV ⟳" in table.get_row(str(cv_only))[0].plain
                assert "CL ⟳" in table.get_row(str(cl_only))[0].plain
            else:
                assert "⟳" in table.get_cell(str(cv_only), "CV")
                assert "⟳" in table.get_cell(str(cl_only), "CL")

    asyncio.run(run())


def test_live_resize_selection_details_and_no_queries(temp_db, monkeypatch):
    seed(temp_db)

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(200, 50)) as pilot:
            table = app.query_one(DataTable)
            app.filter_text = "company"
            app._apply_filter()
            table.move_cursor(row=57)
            await pilot.pause()
            selected = app._selected_app()
            assert table.size.height > 20
            assert app.query_one("#inspector").display
            assert selected["company"] in str(app.query_one("#inspector-content", Static).render())
            queries = Mock(side_effect=AssertionError("resize queried database"))
            for name in ("list_applications_with_status", "get_latest_matches", "get_latest_readiness_batch",
                         "get_job_posting_by_application"):
                monkeypatch.setattr(temp_db, name, queries)
            for width, height in [(40, 12), (60, 15), (79, 24), (80, 24), (119, 24),
                                  (120, 18), (160, 24), (179, 24), (180, 18),
                                  (200, 12), (180, 17), (200, 50)]:
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                assert app._selected_app()["id"] == selected["id"]
                assert app.filter_text == "company"
                assert app.focused is table
                assert table.scroll_y > 0
                row_height = 4 if width < 80 else 1
                selected_top = table.cursor_row * row_height - table.scroll_y + int(table.show_header)
                assert selected_top >= 0
                assert selected_top + row_height <= table.size.height
                assert table.max_scroll_x == 0, (width, height, app.size, table.size, app.mode, app._schema)
                assert app.query_one("#inspector").display == (width >= 180 and height >= 18)
                if width < 80:
                    row = table.get_row(str(selected["id"]))
                    assert len(row) == 1 and len(row[0].plain.splitlines()) == 4
                    assert "draft" in row[0].plain and "Match" in row[0].plain
            await pilot.resize_terminal(40, 12)
            await pilot.press("enter")
            content = str(app.screen.query_one("#text-content", Static).render())
            for value in (selected["company"], selected["role"], "CV profile:", "Source:", "Created:",
                          "Readiness:", "Match:", "JD:", "CV:", "CL:", "Status History:"):
                assert value in content
            await pilot.press("end")
            assert app.screen.query_one("#text-scroll").scroll_y > 0
            screen = app.screen
            for size in [(39, 12), (40, 11)]:
                await pilot.resize_terminal(*size)
                await pilot.press("escape", "s", "D")
                assert app.screen is screen
                assert screen.query_one(ResizeGuard).display
            await pilot.resize_terminal(40, 12)
            await pilot.press("escape")
            assert app._selected_app()["id"] == selected["id"]
            queries.assert_not_called()

    asyncio.run(run())


@pytest.mark.parametrize("size", [(160, 50), (40, 12)])
def test_malformed_url_refresh_highlight_details_and_resize(temp_db, size):
    first = temp_db.insert_application("A", "Engineer", job_url="https://example.com/job")
    malformed = temp_db.insert_application("B", "Engineer", job_url="https://[")
    last = temp_db.insert_application("C", "Engineer", job_url="https://[", source="referral")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=size) as pilot:
            table = app.query_one(DataTable)
            app.action_refresh()
            await pilot.pause()
            assert table.row_count == 3
            assert "DB error" not in app.latest_message
            for app_id in (first, malformed, last):
                table.move_cursor(row=table.get_row_index(str(app_id)))
                await pilot.pause()
                assert app._selected_app()["id"] == app_id
            table.move_cursor(row=table.get_row_index(str(malformed)))
            await pilot.pause()
            await pilot.press("enter")
            details = app.screen
            for dimensions in [(40, 12), (160, 50)]:
                await pilot.resize_terminal(*dimensions)
                await pilot.pause()
                content = str(details.query_one("#text-content", Static).render())
                assert "Source: —" in content and "URL: https://[" in content
                assert app._selected_app()["id"] == malformed
                assert table.row_count == 3
            await pilot.press("escape")
            await pilot.resize_terminal(200, 50)
            await pilot.pause()
            assert table.get_cell(str(first), "Source").plain == "example.com"
            assert table.get_cell(str(malformed), "Source").plain == "—"
            assert table.get_cell(str(last), "Source").plain == "referral"

    asyncio.run(run())


@pytest.mark.parametrize("focus", ["tab", "mouse"])
def test_ordinary_filter_focus_survives_shrink_and_action_letter_typing(temp_db, focus):
    temp_db.insert_application("Company", "Engineer")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            field = app.query_one("#filter-input", Input)
            if focus == "tab":
                await pilot.press("tab")
            else:
                await pilot.click("#filter-input")
            assert app.focused is field
            await pilot.press("C")
            await pilot.resize_terminal(40, 12)
            await pilot.pause()
            assert app.query_one("#filter-bar").display
            assert app.focused is field
            await pilot.press("e", "s", "m", "r")
            assert field.value == "Cesmr"
            assert app.filter_text == "Cesmr"
            assert len(app.screen_stack) == 1
            await pilot.press("escape")
            assert app.focused is app.query_one(DataTable)
            assert not app.query_one("#filter-bar").display

    asyncio.run(run())


def test_thousand_record_navigation_and_resize_smoke(temp_db, monkeypatch):
    import time

    seed(temp_db, 1000)

    async def run():
        app = CvDashboard()
        start = time.perf_counter()
        async with app.run_test(size=(160, 50)) as pilot:
            load_seconds = time.perf_counter() - start
            table = app.query_one(DataTable)
            assert table.row_count == 1000
            await pilot.press("ctrl+end")
            table.move_cursor(row=999)
            await pilot.pause()
            selected = app._selected_app()["id"]
            reloads = Mock(side_effect=AssertionError("resize reloaded data"))
            for name in ["list_applications_with_status", "get_latest_matches", "get_latest_readiness_batch"]:
                monkeypatch.setattr(temp_db, name, reloads)
            starts = Mock(side_effect=AssertionError("resize launched service"))
            for name in ["_regenerate", "_generate_cover_letter", "_score_one", "_run_discovery"]:
                monkeypatch.setattr(app, name, starts)
            start = time.perf_counter()
            for size in [(40, 12), (80, 24), (160, 12), (160, 50)]:
                await pilot.resize_terminal(*size)
                await pilot.pause()
                assert app._selected_app()["id"] == selected
                assert table.scroll_y > 0
                assert table.max_scroll_x == 0
            resize_seconds = time.perf_counter() - start
            await pilot.press("up", "up", "down")
            assert table.cursor_row == 998
            reloads.assert_not_called()
            starts.assert_not_called()
            print(f"1000-record smoke: initial load {load_seconds:.3f}s; four live resizes {resize_seconds:.3f}s")

    asyncio.run(run())
