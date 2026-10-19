"""Synthetic tracker/publication tests; no paid completions or personal source."""

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cv_optimizer import tracker
from cv_optimizer.config import settings


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

    def render(markdown, path):
        Path(path).write_bytes(b"%PDF-fake\n" + markdown.encode())

    renderer = Mock(side_effect=render)
    monkeypatch.setattr(tracker, "PDFGenerator", lambda: SimpleNamespace(generate=renderer))
    monkeypatch.setattr(tracker, "CoverLetterPDFGenerator", lambda: SimpleNamespace(generate=renderer))
    checker = Mock(return_value=None)
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


def test_replacement_renderer_failure_preserves_pair_and_path(generation):
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it")
    path = Path(g.db.get_application(app_id)[4])
    old_pdf = path.read_bytes()
    old_md = path.with_suffix(".md").read_text()
    g.cv.return_value = "## Summary\nReplacement"

    def fail_render(markdown, staged_path):
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


@pytest.mark.parametrize("failure", ["checker", "policy", "renderer"])
def test_failed_initial_attempt_has_no_artifacts_or_ready_path(generation, failure):
    g = generation
    if failure == "checker":
        g.checker.side_effect = ValueError("cv: excluded claim")
    elif failure == "policy":
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


@pytest.mark.parametrize("action,column", [(tracker.reoptimize, 4), (tracker.generate_cover_letter, 8)])
def test_failed_replacement_check_leaves_prior_pair_untouched(generation, action, column):
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    before_app = g.db.get_application(app_id)
    path = Path(before_app[column])
    before_pair = (path.read_bytes(), path.with_suffix(".md").read_bytes())
    g.renderer.reset_mock()
    g.checker.side_effect = ValueError("content check failed: excluded claim")
    with pytest.raises(ValueError, match="excluded claim"):
        action(app_id)
    assert g.db.get_application(app_id) == before_app
    assert (path.read_bytes(), path.with_suffix(".md").read_bytes()) == before_pair
    g.renderer.assert_not_called()


@pytest.mark.parametrize("action,column", [(tracker.reoptimize, 4), (tracker.generate_cover_letter, 8)])
@pytest.mark.parametrize("aba", [False, True])
def test_tracker_captures_revision_before_writer(generation, action, column, aba):
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it", with_cover_letter=True)
    path = Path(g.db.get_application(app_id)[column])
    before = (path.read_bytes(), path.with_suffix(".md").read_bytes())
    def switch(context, jd, language):
        assert context.profile == "it"
        g.db.set_application_profile(app_id, "mechanical_engineering")
        if aba:
            g.db.set_application_profile(app_id, "it")
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
def test_stale_revision_cannot_publish(generation, aba):
    from cv_optimizer.documents import publish_document
    g = generation
    app_id = tracker.track("Acme", "Engineer", str(g.jd), cv_profile="it")
    path = Path(g.db.get_application(app_id)[4])
    before = (path.read_bytes(), path.with_suffix(".md").read_bytes())
    def render_and_switch(markdown, staged):
        g.render(markdown, staged)
        g.db.set_application_profile(app_id, "mechanical_engineering")
        if aba:
            g.db.set_application_profile(app_id, "it")
    with pytest.raises(ValueError, match="profile|revision"):
        publish_document(app_id, "it", 0, "stale", path, render_and_switch, "cv")
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


@pytest.mark.parametrize("outcome", ["tracked", "cv", "rejected_letter", "both", "changed"])
def test_server_reports_actual_current_paths(generation, monkeypatch, outcome):
    import server
    g = generation
    if outcome == "tracked":
        g.cv.side_effect = ValueError("CV rejected")
    elif outcome == "cv":
        g.letter.side_effect = ValueError("letter rejected")
    elif outcome == "rejected_letter":
        g.checker.side_effect = [None, ValueError("cover_letter: excluded claim")]
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
    elif outcome in ("cv", "rejected_letter"):
        assert "CV Ready" in title and "Letter" not in title
        assert "letter" in notify.call_args.kwargs["description"].lower()
    else:
        assert "CV + Cover Letter" in title
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
