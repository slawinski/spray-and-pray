import asyncio
import json

from rich.text import Text
from textual.widgets import Static

from cv_optimizer.tui.app import CvDashboard


def test_detail_hierarchy_keeps_literal_values_and_separates_evidence(temp_db):
    app_id = temp_db.insert_application("Company [red] 界", "Engineer [bold]", cv_profile="it",
                                        cv_path="/applications/[red]/cv.pdf",
                                        job_url="https://example.com/[link=literal]")
    temp_db.insert_status(app_id, "applied")
    record = temp_db.list_applications_with_status()[0]
    app = CvDashboard()
    app.readiness[app_id] = 72
    app.matches[app_id] = {
        "score": 85, "label": "Strong", "confidence": "high",
        "assessment_json": json.dumps({"requirements": [
            {"requirement": "React [red]", "evidence_level": "direct"},
            {"requirement": "TypeScript", "evidence_level": "direct"},
            {"requirement": "Vue", "evidence_level": "framework_transfer", "evidence_values": ["Svelte"]},
            {"requirement": "AWS", "evidence_level": "none"},
        ]}),
    }
    app.discovery_details[app_id] = {
        "posted_at": "2026-10-20", "first_seen_at": "2026-10-22",
        "location_text": "Warsaw [blue]", "work_model": "hybrid", "salary_raw": "20–25k PLN",
    }

    content = app.detail_content(record)
    assert isinstance(content, Text)
    sections = ["Overview", "Match evidence", "Documents", "Job information", "Discovery", "Status History:"]
    positions = [content.plain.index(section) for section in sections]
    assert positions == sorted(positions)
    for label in [record["company"], *sections, "Status:", "CV profile:", "CV:"]:
        position = content.plain.index(label)
        assert any(span.start <= position < span.end and "bold" in str(span.style) for span in content.spans)
    assert "Strong:\n  • React [red]\n  • TypeScript\n" in content.plain
    assert "Transferable:\n  • Vue → Svelte\n" in content.plain
    assert "Gaps:\n  • AWS\n" in content.plain
    assert "CV: ✓ Available\n  /applications/[red]/cv.pdf\n" in content.plain
    for literal in [record["role"], record["job_url"], "Warsaw [blue]", "20–25k PLN"]:
        assert literal in content.plain
    assert "  • applied\n    " in content.plain


def test_formatted_details_are_shared_wrap_and_refresh_without_losing_screen(temp_db):
    app_id = temp_db.insert_application("Company [bold] " + "界" * 30, "Senior Engineer",
                                        cv_profile="it", job_url="https://example.com/" + "long" * 40)
    temp_db.insert_status(app_id, "draft")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(200, 40)) as pilot:
            await pilot.pause()
            inspector = app.query_one("#inspector-content", Static)
            assert inspector.render().spans
            await pilot.press("enter")
            screen = app.screen
            details = screen.query_one("#text-content", Static)
            assert details.render().plain == inspector.render().plain
            assert details.render().spans == inspector.render().spans
            for dimensions in [(40, 12), (200, 40)]:
                await pilot.resize_terminal(*dimensions)
                await pilot.pause()
                assert app.screen is screen
                assert screen.query_one("#text-scroll").max_scroll_x == 0
                assert "Company [bold]" in details.render().plain
                assert details.render().spans
            temp_db.insert_status(app_id, "interview 1")
            app.refresh_apps()
            await pilot.pause()
            assert app.screen is screen
            assert "Status: interview 1" in details.render().plain
            assert details.render().plain == inspector.render().plain
            assert details.render().spans == inspector.render().spans
            await pilot.resize_terminal(40, 12)
            await pilot.press("end")
            assert screen.query_one("#text-scroll").scroll_y > 0
            await pilot.press("escape")
            assert app._selected_app()["id"] == app_id

    asyncio.run(run())
