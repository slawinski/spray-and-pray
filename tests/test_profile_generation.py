"""Synthetic tracker/publication tests; no paid completions or personal source."""

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cv_optimizer import tracker
from cv_optimizer.config import settings
from cv_optimizer.document_validation import DocumentValidator, ValidationResult
from test_profile_prompts import FakeClient


@pytest.fixture()
def generation(tmp_path, monkeypatch, temp_db, temp_apps_dir):
    source = Path(__file__).resolve().parent.parent / "master_cv.example.json"
    master = tmp_path / "source.json"
    master.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(settings, "master_cv_path", str(master))
    monkeypatch.setattr(settings, "candidate_photo_path", "")
    jd = tmp_path / "vacancy.txt"
    jd.write_text("We are hiring an engineer. You will build products with our team.")
    from cv_optimizer.matching import MatchService
    monkeypatch.setattr(MatchService, "score_application", Mock())
    cv = Mock(return_value="## Summary\nApproved CV")
    letter = Mock(return_value="## Example Candidate\nApproved letter")
    monkeypatch.setattr(tracker, "CVOptimizer", lambda **kw: SimpleNamespace(optimize=cv))
    monkeypatch.setattr(tracker, "CoverLetterOptimizer", lambda **kw: SimpleNamespace(generate=letter))

    def render(markdown, path, **kwargs):
        Path(path).write_bytes(b"%PDF-fake\n" + markdown.encode())

    renderer = Mock(side_effect=render)
    monkeypatch.setattr(tracker, "PDFGenerator", lambda: SimpleNamespace(generate=renderer))
    monkeypatch.setattr(tracker, "CoverLetterPDFGenerator", lambda: SimpleNamespace(generate=renderer))
    checker = Mock(return_value=ValidationResult())
    monkeypatch.setattr(tracker, "DocumentValidator", lambda: SimpleNamespace(validate=checker), raising=False)
    return SimpleNamespace(db=temp_db, jd=jd, master=master, cv=cv, letter=letter,
                           renderer=renderer, render=render, checker=checker, apps=temp_apps_dir)


def test_initial_cv_failure_keeps_draft_and_skips_letter(generation):
    g = generation
    g.cv.side_effect = RuntimeError("writer unavailable")
    app_id = tracker.track("Acme", "Engineer", str(g.jd), with_cover_letter=True, cv_profile="it")
    app = g.db.get_application(app_id)
    assert app[3] and Path(app[3]).exists()
    assert app[4] is None and app[8] is None
    assert g.db.get_latest_status(app_id) == "draft"
    g.letter.assert_not_called()


def test_initial_letter_failure_keeps_published_cv(generation):
    g = generation
    g.letter.side_effect = RuntimeError("letter unavailable")
    app_id = tracker.track("Acme", "Engineer", str(g.jd), with_cover_letter=True, cv_profile="it")
    app = g.db.get_application(app_id)
    assert Path(app[4]).exists()
    assert Path(app[4]).with_suffix(".md").exists()
    assert app[8] is None
    assert g.db.get_latest_status(app_id) == "draft"


@pytest.mark.parametrize("profile", ["it", "baker"])
def test_replacement_renderer_failure_preserves_pair_and_path(generation, profile):
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile=profile)
    path = Path(g.db.get_application(app_id)[4])
    old_pdf = path.read_bytes()
    old_md = path.with_suffix(".md").read_text()
    g.cv.return_value = "## Summary\nReplacement"

    def fail_render(markdown, staged_path, **kwargs):
        assert Path(staged_path) != path
        assert path.with_suffix(".md").read_text() == old_md
        assert g.db.get_application(app_id)[4] == str(path)
        Path(staged_path).write_bytes(b"partial render")
        raise OSError("renderer failed")

    g.renderer.side_effect = fail_render
    with pytest.raises(OSError, match="renderer failed"):
        tracker.reoptimize(app_id)
    assert path.read_bytes() == old_pdf
    assert path.with_suffix(".md").read_text() == old_md
    assert g.db.get_application(app_id)[4] == str(path)
    assert sorted(p.name for p in path.parent.iterdir()) == sorted([path.name, path.with_suffix(".md").name, "engineer.txt"])


@pytest.mark.parametrize("profile", [None, "", "unknown"])
def test_new_track_requires_selection_before_any_mutation(generation, monkeypatch, profile):
    init = Mock(side_effect=AssertionError("must not initialize database"))
    monkeypatch.setattr(generation.db, "init_db", init)
    with pytest.raises(ValueError, match="profile"):
        tracker.track("Acme", "Engineer", str(generation.jd), cv_profile=profile)
    init.assert_not_called()
    assert not generation.apps.exists()


def test_omitted_selection_is_rejected(generation):
    with pytest.raises(ValueError, match="profile"):
        tracker.track("Acme", "Engineer", str(generation.jd))
    assert generation.db.list_applications() == []


def test_interleaved_profiles_and_override_are_projected_and_checked(generation):
    from cv_optimizer.profiles import ProfileContext, resolve_profile
    g = generation
    eng = tracker.track("Engineering", "Engineer", str(g.jd), cv_profile="mechanical_engineering", with_cover_letter=True)
    tracker.track("Software", "Developer", str(g.jd), cv_profile="it")
    override = g.master.parent / "override.json"
    source = json.loads(g.master.read_text())
    source["profiles"]["mechanical_engineering"]["summary"] = "Approved override narrative"
    override.write_text(json.dumps(source))
    tracker.reoptimize(eng, str(override))
    tracker.generate_cover_letter(eng, str(override))
    assert [call.args[0].profile for call in g.cv.call_args_list] == ["mechanical_engineering", "it", "mechanical_engineering"]
    assert [call.args[0].profile for call in g.letter.call_args_list] == ["mechanical_engineering"] * 2
    assert g.cv.call_args.args[0] == resolve_profile(source, "mechanical_engineering")
    assert all(isinstance(call.args[0], ProfileContext) for call in g.cv.call_args_list)
    for write, check in zip([g.cv.call_args_list[0], g.letter.call_args_list[0], g.cv.call_args_list[1], g.cv.call_args_list[2], g.letter.call_args_list[1]], g.checker.call_args_list):
        assert check.args[1] == write.args[0]
        assert check.args[3] == write.kwargs["language"]
    assert [c.args[2] for c in g.checker.call_args_list] == ["cv", "cover_letter", "cv", "cv", "cover_letter"]
    assert g.db.get_application_profile(eng) == ("mechanical_engineering", 0)


@pytest.mark.parametrize("action", [tracker.reoptimize, tracker.generate_cover_letter])
def test_unselected_draft_blocks_writers(generation, action):
    g = generation
    app_id = g.db.insert_application("Imported", "Engineer", jd_path=str(g.jd))
    with pytest.raises(ValueError, match="profile|select"):
        action(app_id)
    g.cv.assert_not_called()
    g.letter.assert_not_called()
    g.renderer.assert_not_called()


@pytest.mark.parametrize("failure", ["policy", "renderer"])
def test_failed_initial_attempt_has_no_artifacts_or_ready_path(generation, failure):
    g = generation
    if failure == "policy":
        g.master.write_text('{}')
    else:
        def broken_render(markdown, path):
            Path(path).write_bytes(b"partial")
            raise OSError("render failed")
        g.renderer.side_effect = broken_render
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    app = g.db.get_application(app_id)
    assert app[4] is None and app[8] is None
    assert g.db.get_latest_status(app_id) == "draft"
    assert [p.name for p in Path(app[3]).parent.iterdir()] == ["engineer.txt"]
    g.letter.assert_not_called()


def test_later_letter_allowed_without_cv(generation):
    g = generation
    app_id = g.db.insert_application("Imported", "Engineer", jd_path=str(g.jd), cv_profile="mechanical_engineering")
    path = tracker.generate_cover_letter(app_id)
    assert Path(path).exists()
    assert g.db.get_application(app_id)[4] is None
    assert g.db.get_application(app_id)[8] == path


def test_cv_only_metadata_takes_effect_on_regeneration_not_saved_documents(generation):
    g = generation
    source = json.loads(g.master.read_text())
    source["profiles"]["mechanical_engineering"].pop("cv_role_detail", None)
    g.master.write_text(json.dumps(source))
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="mechanical_engineering",
                           with_cover_letter=True)
    letter_before = g.letter.call_args.args[0]
    pdf = Path(g.db.get_application(app_id)[4])
    before = (pdf.read_bytes(), pdf.with_suffix(".md").read_bytes())
    source["profiles"]["mechanical_engineering"]["cv_role_detail"] = {"software": "ledger"}
    g.master.write_text(json.dumps(source))
    assert (pdf.read_bytes(), pdf.with_suffix(".md").read_bytes()) == before
    tracker.reoptimize(app_id)
    cv_context = g.cv.call_args.args[0]
    assert cv_context.facts["experience"][0]["achievements"] == []
    assert cv_context.rules["role_detail"]["software"] == "ledger"
    assert g.checker.call_args.args[1] == cv_context
    tracker.generate_cover_letter(app_id)
    assert g.letter.call_args.args[0] == letter_before
    assert g.checker.call_args.args[1] == letter_before


def test_migrated_application_regenerates_as_it_after_enrichment(generation, monkeypatch):
    g = generation
    monkeypatch.setattr(g.db, "DB_PATH", g.master.parent / "legacy.db")
    old_pdf = g.master.parent / "legacy.pdf"
    old_md = old_pdf.with_suffix(".md")
    old_pdf.write_bytes(b"legacy PDF")
    old_md.write_text("legacy Markdown")
    with sqlite3.connect(g.db.DB_PATH) as conn:
        conn.execute("""CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL,
            role TEXT NOT NULL, jd_path TEXT, cv_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        app_id = conn.execute(
            "INSERT INTO applications (company, role, jd_path, cv_path) VALUES (?, ?, ?, ?)",
            ("Legacy", "Engineer", str(g.jd), str(old_pdf)),
        ).lastrowid
    g.db.init_db()
    assert old_pdf.read_bytes() == b"legacy PDF"
    assert old_md.read_text() == "legacy Markdown"
    source = json.loads(g.master.read_text())
    source["experience"][1]["achievements"].append("Additional engineering-only history")
    g.master.write_text(json.dumps(source))
    tracker.reoptimize(app_id)
    context = g.cv.call_args.args[0]
    assert context.profile == "it"
    assert [role["id"] for role in context.facts["experience"]] == ["software"]
    assert "Additional engineering-only history" not in json.dumps(context.facts)
    assert g.db.get_application_profile(app_id) == ("it", 0)
    assert Path(g.db.get_application(app_id)[4]).is_file()


@pytest.mark.parametrize("profile", ["it", "mechanical_engineering", "baker"])
@pytest.mark.parametrize("verdict", [
    '{"passed": false, "violations": [{"quote": "PRIVATE EXCERPT", "reason": "PRIVATE REASON"}]}',
    "malformed verdict", TimeoutError("PRIVATE PROVIDER ERROR"),
])
def test_advisory_check_publishes_all_document_flows(generation, monkeypatch, caplog, profile, verdict):
    g = generation
    client = FakeClient(*([verdict] * 4))
    monkeypatch.setattr(tracker, "DocumentValidator", lambda: DocumentValidator(client=client))
    warnings = []
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile=profile,
                           with_cover_letter=True, on_warning=warnings.append)
    g.cv.return_value = "## Summary\nReplacement CV"
    g.letter.return_value = "## Candidate\nReplacement letter"
    tracker.reoptimize(app_id, on_warning=warnings.append)
    tracker.generate_cover_letter(app_id, on_warning=warnings.append)
    app = g.db.get_application(app_id)
    for column, expected in [(4, g.cv.return_value), (8, g.letter.return_value)]:
        path = Path(app[column])
        assert path.read_bytes() == b"%PDF-fake\n" + expected.encode()
        assert path.with_suffix(".md").read_text() == expected
    assert len(warnings) == len(client.requests) == 4
    assert all("Content check" in warning and "PRIVATE" not in warning for warning in warnings)
    expected_detail = "JSON" if verdict == "malformed verdict" else "PRIVATE"
    assert expected_detail in caplog.text


def test_checker_constructor_and_warning_delivery_failure_do_not_block(generation, monkeypatch, caplog):
    g = generation
    monkeypatch.setattr(tracker, "DocumentValidator", Mock(side_effect=RuntimeError("checker unavailable")))
    notify = Mock(side_effect=RuntimeError("notification unavailable"))
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it",
                           with_cover_letter=True, on_warning=notify)
    assert all(Path(g.db.get_application(app_id)[col]).exists() for col in (4, 8))
    assert notify.call_count == 2
    assert "checker unavailable" in caplog.text
    assert "notification" in caplog.text


@pytest.mark.parametrize("later_letter", [False, True])
@pytest.mark.parametrize("delivery_fails", [False, True])
def test_server_advisory_completion_is_safe_and_best_effort(generation, monkeypatch, caplog,
                                                          later_letter, delivery_fails):
    import server
    g = generation
    g.checker.side_effect = RuntimeError("PRIVATE EXCERPT AND PROVIDER ERROR")
    notify = Mock(side_effect=RuntimeError("delivery failed") if delivery_fails else None)
    desktop = Mock(side_effect=RuntimeError("desktop failed") if delivery_fails else None)
    monkeypatch.setattr(server, "send_discord_notification", notify)
    monkeypatch.setattr(server.os, "system", desktop)
    if later_letter:
        app_id = g.db.insert_application("Acme", "Engineer", jd_path=str(g.jd), cv_profile="it")
        server._run_cover_letter_generation(app_id)
    else:
        server.run_cv_optimizer("Acme", "Engineer", g.jd.read_text(), cv_profile="it")
        app_id = g.db.list_applications()[0][0]
    assert Path(g.db.get_application(app_id)[8]).exists()
    assert notify.call_count == desktop.call_count == 1
    assert "incomplete" in notify.call_args.kwargs["description"]
    assert "PRIVATE" not in str(notify.call_args) + str(desktop.call_args)
    assert "Generation Failed" not in str(notify.call_args)
    assert "PRIVATE" in caplog.text


@pytest.mark.parametrize("key,ready", [("ctrl+r", "CV regenerated"), ("ctrl+g", "Cover letter generated")])
def test_tui_pilot_publishes_with_visible_advisory(generation, monkeypatch, key, ready):
    import asyncio
    from textual.widgets import Static
    from cv_optimizer.tui.app import CvDashboard

    g = generation
    client = FakeClient('{"passed": false, "violations": [{"quote": "PRIVATE", "reason": "unsupported"}]}')
    monkeypatch.setattr(tracker, "DocumentValidator", lambda: DocumentValidator(client=client))
    app_id = g.db.insert_application("Acme", "Engineer", jd_path=str(g.jd), cv_profile="it")
    g.db.insert_status(app_id, "draft")

    async def run():
        app = CvDashboard()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press(key)
            await pilot.click("#yes")
            await app.workers.wait_for_complete()
            await pilot.pause()
            status = str(app.query_one("#status-bar", Static).render())
            assert ready in status and "Content check warnings" in status
            assert status.index("Content check warnings") < status.index(ready)
            assert "PRIVATE" not in status and "failed" not in status.lower()

    asyncio.run(run())
    column = 4 if key == "ctrl+r" else 8
    assert Path(g.db.get_application(app_id)[column]).exists()


@pytest.mark.parametrize("action,column", [(tracker.reoptimize, 4), (tracker.generate_cover_letter, 8)])
@pytest.mark.parametrize("aba", [False, True])
@pytest.mark.parametrize("profile", ["it", "baker"])
def test_tracker_captures_revision_before_writer(generation, action, column, aba, profile):
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile=profile, with_cover_letter=True)
    path = Path(g.db.get_application(app_id)[column])
    before = (path.read_bytes(), path.with_suffix(".md").read_bytes())
    def switch(context, jd, language):
        assert context.profile == profile
        g.db.set_application_profile(app_id, "it" if profile == "baker" else "mechanical_engineering")
        if aba:
            g.db.set_application_profile(app_id, profile)
        return "stale generated Markdown"
    writer = g.cv if column == 4 else g.letter
    writer.side_effect = switch
    with pytest.raises(ValueError, match="profile/revision changed"):
        action(app_id)
    assert g.db.get_application(app_id)[4] is None
    assert g.db.get_application(app_id)[8] is None
    assert (path.read_bytes(), path.with_suffix(".md").read_bytes()) == before


@pytest.mark.parametrize("document_type,column", [("cv", 4), ("cover_letter", 8)])
@pytest.mark.parametrize("failure", ["rename_first", "rename_second", "database", "commit"])
def test_publication_failure_restores_pair_and_database(generation, monkeypatch, document_type, column, failure):
    from cv_optimizer.documents import publish_document
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    path = Path(g.db.get_application(app_id)[column])
    md = path.with_suffix(".md")
    before = (md.read_bytes(), path.read_bytes())
    original_replace = Path.replace
    count = 0
    def replace(self, target):
        nonlocal count
        if Path(target) in (md, path):
            count += 1
            if count == (1 if failure == "rename_first" else 2):
                raise OSError("promotion failed")
        return original_replace(self, target)
    if failure.startswith("rename"):
        monkeypatch.setattr(Path, "replace", replace)
    elif failure == "database":
        with g.db.connect() as conn:
            conn.execute("CREATE TRIGGER fail_publish BEFORE UPDATE OF cv_path, cover_letter_path ON applications BEGIN SELECT RAISE(ABORT, 'database failed'); END")
    else:
        connect = g.db.connect
        class CommitFailure:
            def __init__(self):
                self.conn = connect()
            def __getattr__(self, name):
                return getattr(self.conn, name)
            def commit(self):
                raise OSError("commit failed")
        monkeypatch.setattr(g.db, "connect", CommitFailure)
    with pytest.raises(Exception, match="failed"):
        publish_document(app_id, "it", 0, "replacement", path, g.render, document_type)
    assert (md.read_bytes(), path.read_bytes()) == before
    assert g.db.get_application(app_id)[column] == str(path)
    assert not any(p.is_dir() for p in path.parent.iterdir())


@pytest.mark.parametrize("aba", [False, True])
@pytest.mark.parametrize("profile", ["it", "baker"])
def test_stale_revision_cannot_publish(generation, aba, profile):
    from cv_optimizer.documents import publish_document
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile=profile)
    path = Path(g.db.get_application(app_id)[4])
    before = (path.read_bytes(), path.with_suffix(".md").read_bytes())
    def render_and_switch(markdown, staged):
        g.render(markdown, staged)
        g.db.set_application_profile(app_id, "it" if profile == "baker" else "mechanical_engineering")
        if aba:
            g.db.set_application_profile(app_id, profile)
    with pytest.raises(ValueError, match="profile|revision"):
        publish_document(app_id, profile, 0, "stale", path, render_and_switch, "cv")
    assert (path.read_bytes(), path.with_suffix(".md").read_bytes()) == before
    assert g.db.get_application(app_id)[4] is None
    assert not any(p.is_dir() for p in path.parent.iterdir())


def test_initial_letter_does_not_silently_follow_changed_profile(generation, monkeypatch):
    g = generation
    def publish_then_switch(*args, **kwargs):
        result = publish(*args, **kwargs)
        g.db.set_application_profile(args[0], "mechanical_engineering")
        return result
    publish = getattr(tracker, "publish_document", None)
    monkeypatch.setattr(tracker, "publish_document", publish_then_switch, raising=False)
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    g.letter.assert_not_called()
    assert g.db.get_application_profile(app_id) == ("mechanical_engineering", 1)
    assert g.db.get_application(app_id)[4] is None


@pytest.mark.parametrize("outcome", ["tracked", "cv", "warning_letter", "both", "changed"])
def test_server_reports_actual_current_paths(generation, monkeypatch, outcome):
    import server
    g = generation
    if outcome == "tracked":
        g.cv.side_effect = ValueError("CV rejected")
    elif outcome == "cv":
        g.letter.side_effect = ValueError("letter rejected")
    elif outcome == "warning_letter":
        g.checker.side_effect = [ValidationResult(), ValidationResult(("PRIVATE EXCERPT",))]
    elif outcome == "changed":
        def switch(context, jd, language):
            app_id = g.db.list_applications()[0][0]
            g.db.set_application_profile(app_id, "mechanical_engineering")
            return "stale letter"
        g.letter.side_effect = switch
    notify = Mock()
    desktop = Mock()
    monkeypatch.setattr(server, "send_discord_notification", notify)
    monkeypatch.setattr(server.os, "system", desktop)
    server.run_cv_optimizer("Acme", "Engineer", g.jd.read_text(), cv_profile="it")
    title = notify.call_args.kwargs["title"]
    if outcome in ("tracked", "changed"):
        assert "Tracked" in title and "ready" not in title.lower()
    elif outcome == "cv":
        assert "CV Ready" in title and "Letter" not in title
        assert "letter" in notify.call_args.kwargs["description"].lower()
    else:
        assert "CV + Cover Letter" in title
        if outcome == "warning_letter":
            assert "warning" in notify.call_args.kwargs["description"].lower()
            assert "PRIVATE" not in str(notify.call_args)
    assert notify.call_count == desktop.call_count == 1


def test_real_pdf_render_after_positive_check(generation, monkeypatch):
    from cv_optimizer.generator import PDFGenerator
    from cv_optimizer.cover_letter import CoverLetterPDFGenerator
    g = generation
    monkeypatch.setattr(tracker, "PDFGenerator", PDFGenerator)
    monkeypatch.setattr(tracker, "CoverLetterPDFGenerator", CoverLetterPDFGenerator)
    g.cv.return_value = "## Personal Info\n### Example Candidate\nexample@example.com\n\n## Summary\nSoftware engineer.\n\n## Experience\n### Software Engineer\nExample Software | 2020 - Present\n- Built reliable services.\n\n## Education\nMSc Mechanical Engineering\n"
    g.letter.return_value = "## Example Candidate\n### Contact\nexample@example.com\n\nDear Hiring Manager,\n\nI build reliable services.\n\nSincerely,\nExample Candidate"
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    app = g.db.get_application(app_id)
    assert g.checker.call_count == 2
    for path in (app[4], app[8]):
        assert Path(path).read_bytes().startswith(b"%PDF-")
        assert Path(path).stat().st_size > 1000


def test_tracker_publishes_real_ledger_pdf_with_prepared_cv_context(generation, monkeypatch):
    import fitz
    from cv_optimizer.generator import PDFGenerator
    from cv_optimizer.optimizer import CVOptimizer
    from cv_optimizer.profiles import resolve_profile
    from test_cv_ledger import many_role_source, source_markdown, normalized_text

    g = generation
    source = many_role_source()
    g.master.write_text(json.dumps(source))
    cv = CVOptimizer("http://fake", "fake", "fake")
    client = FakeClient(source_markdown(resolve_profile(source, "mechanical_engineering")))
    cv.client = client
    monkeypatch.setattr(tracker, "CVOptimizer", lambda **kw: cv)
    monkeypatch.setattr(tracker, "PDFGenerator", PDFGenerator)
    app_id = tracker.track("Synthetic Works", "Engineer", str(g.jd), cv_profile="mechanical_engineering")
    path = Path(g.db.get_application(app_id)[4])
    assert path.with_suffix(".md").read_text().count("> **") == 7
    assert "IT achievement sentinel" not in client.requests[0]["messages"][1]["content"]
    assert g.checker.call_args.args[1].rules["role_detail"]["role-0"] == "ledger"
    with fitz.open(path) as doc:
        text = normalized_text(doc)
        assert "IT achievement sentinel" not in text
        assert all(role["title"] in text for role in source["experience"])
        assert "Designed engineering fixture 7." in text


@pytest.mark.parametrize("language", ["en", "pl"])
def test_baker_real_publication_interleaved_and_regenerated(generation, monkeypatch, language):
    import fitz
    from cv_optimizer.generator import PDFGenerator
    from cv_optimizer.cover_letter import CoverLetterPDFGenerator
    from cv_optimizer.profiles import resolve_profile
    from test_generator import _make_test_image
    g = generation
    photo = g.master.parent / "synthetic.png"
    _make_test_image(str(photo))
    monkeypatch.setattr(settings, "candidate_photo_path", str(photo))
    monkeypatch.setattr(tracker, "PDFGenerator", PDFGenerator)
    monkeypatch.setattr(tracker, "CoverLetterPDFGenerator", CoverLetterPDFGenerator)
    g.jd.write_text("Szukamy początkującego piekarza. Oferujemy pracę i szkolenie. Wymagania: obsługa pieców oraz aktualne badania sanitarne."
                    if language == "pl" else "We are seeking a trainee baker for our team. Commercial ovens and sanitary clearance required.")
    practice, workshop, employment = (("Domowy wypiek chleba", "Warsztaty", "Dotychczasowa praca zawodowa")
                                      if language == "pl" else ("Home Baking Practice", "Workshops", "Other Employment"))
    g.cv.return_value = (f"# Jane Doe\n### Aspiring Baker\n## Summary\nHome hobbyist seeking trainee work.\n"
                         f"## {practice}\nHobby, early 2023. More than 40 bakes, mostly country loaves, up to three per batch. Bread for friends on shared trips.\n"
                         f"## {workshop}\nBread basics, Example Baking Studio, June 2025, Alex Example.\n"
                         f"## {employment}\nPrevious career in software and mechanical engineering; now moving into baking.\n"
                         "## Education\n**State University**\n\nMSc in Mechanical Engineering\n"
                         "## Portfolio\n[Home baking portfolio](https://example.com/baking)\n\n"
                         "[Crumb Companion](https://example.com/sourdough-assistant)\n\nBuilt a sourdough assistant with fermentation and hydration calculators.\n")
    g.letter.return_value = "## Jane Doe\n\n" + ("Szanowni Państwo," if language == "pl" else "Dear Hiring Manager,") + "\n\nHome baking hobbyist seeking trainee work.\n\nJane Doe"
    baker = tracker.track("Example Bakery", "Trainee", str(g.jd), cv_profile="baker", with_cover_letter=True)
    with fitz.open(g.db.get_application(baker)[4]) as doc:
        assert sum(len(p.get_image_info()) for p in doc) == 1
    tracker.track("Example Software", "Developer", str(g.jd), cv_profile="it")
    tracker.track("Example Engineering", "Engineer", str(g.jd), cv_profile="mechanical_engineering")
    tracker.reoptimize(baker)
    tracker.generate_cover_letter(baker)
    assert [c.args[0].profile for c in g.cv.call_args_list] == ["baker", "it", "mechanical_engineering", "baker"]
    assert [c.args[0].profile for c in g.letter.call_args_list] == ["baker", "baker"]
    source = json.loads(g.master.read_text())
    for write in (g.cv.call_args_list[0], g.cv.call_args_list[-1], *g.letter.call_args_list):
        kind = "cover_letter" if write in g.letter.call_args_list else "cv"
        assert write.args[0] == resolve_profile(source, "baker", document_type=kind)
        assert write.kwargs["language"] == language
    assert [c.args[2] for c in g.checker.call_args_list] == ["cv", "cover_letter", "cv", "cv", "cv", "cover_letter"]
    assert all(c.args[3] == language for c in g.checker.call_args_list)
    app = g.db.get_application(baker)
    with fitz.open(app[4]) as doc:
        text = " ".join(p.get_text() for p in doc)
        assert all(word in text for word in (practice, workshop, employment, "Previous career", "Crumb Companion", "State University"))
        assert "Tech Corp" not in text and "Example Pumps" not in text
        assert sum(len(p.get_image_info()) for p in doc) == 1
        assert any(l.get("uri") == "https://example.com/baking" for p in doc for l in p.get_links())
        assert any(l.get("uri") == "https://example.com/sourdough-assistant" for p in doc for l in p.get_links())
    with fitz.open(app[8]) as doc:
        assert "Jane Doe" in doc[0].get_text()
    assert g.db.get_application_profile(baker) == ("baker", 0)


def test_unprepared_baker_fails_before_writer_and_keeps_draft(generation):
    g = generation
    source = json.loads(g.master.read_text())
    del source["profiles"]["baker"]
    g.master.write_text(json.dumps(source))
    app_id = tracker.track("Bakery", "Trainee", str(g.jd), cv_profile="baker", with_cover_letter=True)
    assert g.db.get_latest_status(app_id) == "draft"
    assert g.db.get_application(app_id)[4] is None and g.db.get_application(app_id)[8] is None
    g.cv.assert_not_called()
    g.letter.assert_not_called()
    g.renderer.assert_not_called()
