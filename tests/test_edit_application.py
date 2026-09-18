"""Tests for tracker.edit_application (correcting company/role/URL + FS rename)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_tracked_app(db, apps_dir, master_cv_path, company="Acme", role="Frontend Dev"):
    """Builds a DB record + on-disk layout exactly like track() would."""
    from cv_optimizer import tracker

    app_id = db.insert_application(company, role, job_url="https://example.com/jobs/1")
    db.insert_status(app_id, "draft")

    app_dir = tracker._build_app_dir(app_id, company, role)
    assert str(app_dir).startswith(str(apps_dir))
    app_dir.mkdir(parents=True)

    name = json.loads(Path(master_cv_path).read_text(encoding="utf-8"))["personal_info"]["name"]
    base = tracker._build_cv_filename(name, role)

    jd = app_dir / f"{tracker._clean_role_stem(role)}.pdf"
    jd.write_bytes(b"%PDF-fake-jd")
    cv_md = app_dir / f"{base}.md"
    cv_md.write_text("# CV")
    cv_pdf = app_dir / f"{base}.pdf"
    cv_pdf.write_bytes(b"%PDF-fake-cv")
    cl_md = app_dir / f"{base}_Cover_Letter.md"
    cl_md.write_text("# CL")
    cl_pdf = app_dir / f"{base}_Cover_Letter.pdf"
    cl_pdf.write_bytes(b"%PDF-fake-cl")

    db.update_application(app_id, jd_path=str(jd), cv_path=str(cv_pdf), cover_letter_path=str(cl_pdf))
    return app_id, app_dir


def _history(db, app_id):
    return [row[1] for row in db.get_status_history_with_ids(app_id)]


def test_edit_company_and_role_renames_everything(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    app_id, old_dir = _make_tracked_app(db, temp_apps_dir, master_cv)

    result = tracker.edit_application(app_id, company="Acme Corp", role="Backend Dev")

    new_dir = tracker._build_app_dir(app_id, "Acme Corp", "Backend Dev")
    assert not old_dir.exists()
    assert new_dir.is_dir()
    assert (new_dir / "backend_dev.pdf").is_file()
    assert (new_dir / "Test_Candidate_Backend_Dev.md").is_file()
    assert (new_dir / "Test_Candidate_Backend_Dev.pdf").is_file()
    assert (new_dir / "Test_Candidate_Backend_Dev_Cover_Letter.md").is_file()
    assert (new_dir / "Test_Candidate_Backend_Dev_Cover_Letter.pdf").is_file()

    app = db.get_application(app_id)
    assert app[1] == "Acme Corp"
    assert app[2] == "Backend Dev"
    assert app[3] == str(new_dir / "backend_dev.pdf")
    assert app[4] == str(new_dir / "Test_Candidate_Backend_Dev.pdf")
    assert app[8] == str(new_dir / "Test_Candidate_Backend_Dev_Cover_Letter.pdf")
    assert result["company"] == "Acme Corp"
    # Status history untouched by a rename.
    assert _history(db, app_id) == ["draft"]


def test_edit_company_only_keeps_filenames(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    app_id, old_dir = _make_tracked_app(db, temp_apps_dir, master_cv)

    tracker.edit_application(app_id, company="Acme Corp")

    new_dir = tracker._build_app_dir(app_id, "Acme Corp", "Frontend Dev")
    assert not old_dir.exists()
    assert (new_dir / "frontend_dev.pdf").is_file()
    assert (new_dir / "Test_Candidate_Frontend_Dev.pdf").is_file()

    app = db.get_application(app_id)
    assert app[1] == "Acme Corp"
    assert app[2] == "Frontend Dev"
    assert app[3] == str(new_dir / "frontend_dev.pdf")


def test_edit_job_url_only_leaves_filesystem_alone(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    app_id, old_dir = _make_tracked_app(db, temp_apps_dir, master_cv)
    before = sorted(p.name for p in old_dir.iterdir())

    tracker.edit_application(app_id, job_url="https://example.com/jobs/2")

    assert old_dir.is_dir()
    assert sorted(p.name for p in old_dir.iterdir()) == before
    assert db.get_application(app_id)[5] == "https://example.com/jobs/2"

    # Empty string clears the URL.
    tracker.edit_application(app_id, job_url="   ")
    assert db.get_application(app_id)[5] is None


def test_edit_duplicate_blocked(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    _make_tracked_app(db, temp_apps_dir, master_cv, company="Acme", role="Frontend Dev")
    other_id, _ = _make_tracked_app(db, temp_apps_dir, master_cv, company="Beta", role="Backend Dev")

    with pytest.raises(ValueError, match="already tracked"):
        tracker.edit_application(other_id, company="Acme", role="Frontend Dev")


def test_edit_rejects_bad_input(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    app_id, _ = _make_tracked_app(db, temp_apps_dir, master_cv)

    with pytest.raises(ValueError, match="not found"):
        tracker.edit_application(9999, company="Nope")

    with pytest.raises(ValueError, match="must not be empty"):
        tracker.edit_application(app_id, company="   ")

    with pytest.raises(ValueError, match="must not be empty"):
        tracker.edit_application(app_id, role="")


def test_edit_missing_dir_recreates_layout(temp_db, temp_apps_dir, master_cv):
    import shutil

    from cv_optimizer import tracker

    db = temp_db
    app_id, old_dir = _make_tracked_app(db, temp_apps_dir, master_cv)
    shutil.rmtree(old_dir)

    tracker.edit_application(app_id, company="Acme Corp")

    new_dir = tracker._build_app_dir(app_id, "Acme Corp", "Frontend Dev")
    assert new_dir.is_dir()
    app = db.get_application(app_id)
    assert app[1] == "Acme Corp"
    assert app[3] == str(new_dir / "frontend_dev.pdf")


def test_edit_noop_changes_nothing(temp_db, temp_apps_dir, master_cv):
    from cv_optimizer import tracker

    db = temp_db
    app_id, old_dir = _make_tracked_app(db, temp_apps_dir, master_cv)

    result = tracker.edit_application(app_id, company="Acme", role="Frontend Dev")

    assert old_dir.is_dir()
    assert result["company"] == "Acme"
    assert _history(db, app_id) == ["draft"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
