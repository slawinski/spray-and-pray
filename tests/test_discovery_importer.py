"""DraftImporter tests — threshold, draft state, assessment copy, dedupe,
deletion/dismissal lifecycle. No LLM calls anywhere."""

import json
from pathlib import Path

import pytest

from cv_optimizer import db, tracker
from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.importer import DraftImporter, ImportError_, build_jd_file_content
from cv_optimizer.matching import jd_hash

from conftest import make_job

ASSESSMENT_JSON = json.dumps({"role_family": "frontend", "requirements": []})


def _insert_posting(
    *,
    description: str | None = None,
    role: str = "Senior Frontend Engineer",
    company: str = "Dash0",
    canonical_url: str = "https://careers.dash0.com/jobs/123",
    active_state: str = "active",
    prefilter_state: str = "pass",
    user_state: str = "pending",
    **kwargs,
) -> int:
    if description is None:
        description = (
            "We are looking for a Senior Frontend Engineer to build complex "
            "user interfaces with React and TypeScript. Strong product "
            "collaboration, accessibility, and design systems experience "
            "required. 5+ years of frontend engineering experience. Hybrid "
            "work model with an office in Warsaw, Poland."
        )
    return db.insert_job_posting(
        company=company,
        role=role,
        description=description,
        description_hash=jd_hash(description),
        canonical_url=canonical_url,
        location_text="Warsaw, Poland",
        work_model="hybrid",
        remote_scope="unknown",
        seniority="senior",
        active_state=active_state,
        active_confidence="high",
        company_norm=company.lower(),
        role_norm=role.lower(),
        location_norm="warsaw poland",
    )


def _insert_assessment(posting_id: int, score: int = 94) -> int:
    return db.insert_job_match_assessment(
        job_posting_id=posting_id,
        score=score,
        label="STRONG",
        confidence="HIGH",
        base_score=94.0,
        assessment_json=ASSESSMENT_JSON,
        candidate_hash="candidate-hash",
        jd_hash=jd_hash("test jd"),
        scoring_version="match-v2",
        prompt_version="match-prompt-v2",
        model_name="test-model",
    )


def _make_importer(config=None) -> DraftImporter:
    return DraftImporter(config or DiscoveryConfig())


# ── Threshold / qualification ────────────────────────────────────────────────

def test_score_85_imports_draft(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=85)

    result = _make_importer().import_job(posting_id)
    app_id = result["application_id"]

    app = db.get_application(app_id)
    assert app is not None
    # applications tuple: id, company, role, jd_path, cv_path, job_url, created_at, source, cover_letter_path
    assert app[1] == "Dash0"
    assert app[2] == "Senior Frontend Engineer"
    assert app[3] is not None and Path(app[3]).exists()  # jd_path
    assert app[4] is None  # cv_path
    assert app[8] is None  # cover_letter_path
    assert app[5] == "https://careers.dash0.com/jobs/123"  # job_url
    assert app[7] == "auto:serpapi" or app[7] == "auto:discovery"

    assert db.get_latest_status(app_id) == "draft"
    db.init_db()
    assert db.get_application_profile(app_id) == (None, 0)

    job = db.get_job_posting(posting_id)
    assert job["application_id"] == app_id
    assert job["user_state"] == "imported"
    assert job["imported_at"] is not None

    # The application carries the copied assessment.
    match = db.get_latest_match(app_id)
    assert match is not None
    assert match["score"] == 85


def test_score_84_creates_no_application(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=84)

    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)

    assert db.get_job_posting(posting_id)["application_id"] is None
    assert len(db.list_applications()) == 0


def test_inactive_high_score_creates_no_application(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting(active_state="inactive")
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=95)

    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)
    assert len(db.list_applications()) == 0


def test_prefilter_failed_creates_no_application(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "fail", "role:backend")
    _insert_assessment(posting_id, score=95)

    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)
    assert len(db.list_applications()) == 0


def test_dismissed_posting_never_imports(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=95)
    db.set_job_user_state(posting_id, "dismissed")

    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)
    assert len(db.list_applications()) == 0


def test_missing_assessment_creates_no_application(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)
    assert len(db.list_applications()) == 0


# ── Assessment copy (no LLM) ─────────────────────────────────────────────────

def test_import_copies_assessment_without_llm(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    result = _make_importer().import_job(posting_id)
    assert result["assessment_copied"] is True

    app_id = result["application_id"]
    app_match = db.get_latest_match(app_id)
    job_match = db.get_latest_job_match(posting_id)
    assert app_match["score"] == 94 == job_match["score"]
    assert app_match["assessment_json"] == job_match["assessment_json"]
    # Identity metadata copied; jd_hash reflects the stored JD file.
    assert app_match["scoring_version"] == "match-v2"
    assert app_match["prompt_version"] == "match-prompt-v2"


def test_reimport_is_idempotent(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    first = _make_importer().import_job(posting_id)
    second = _make_importer().import_job(posting_id)
    assert second["application_id"] == first["application_id"]
    assert second.get("already_imported") is True
    assert len(db.list_applications()) == 1


# ── Existing manual application dedupe ───────────────────────────────────────

def test_existing_manual_application_links_without_duplicate(temp_db, temp_apps_dir, master_cv):
    # Manual application with the same vacancy (same company/role/equivalent JD).
    app_id = db.insert_application("Dash0", "Senior Frontend Engineer", job_url="https://careers.dash0.com/jobs/123")
    db.insert_status(app_id, "draft")

    posting_id = _insert_posting(company="Dash0", role="Senior Frontend Engineer")
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=96)

    result = _make_importer().import_job(posting_id)
    assert result["application_id"] == app_id
    assert result["linked_existing"] is True

    assert len(db.list_applications()) == 1  # no duplicate
    job = db.get_job_posting(posting_id)
    assert job["application_id"] == app_id
    assert job["user_state"] == "imported"


# ── Deletion / dismissal lifecycle ───────────────────────────────────────────

def test_delete_auto_draft_dismisses_posting_and_prevents_reimport(
    temp_db, temp_apps_dir, master_cv
):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    result = _make_importer().import_job(posting_id)
    app_id = result["application_id"]

    tracker.remove_application(app_id)

    job = db.get_job_posting(posting_id)
    assert job["application_id"] is None  # FK SET NULL
    assert job["user_state"] == "dismissed"
    assert job["dismissed_at"] is not None

    # A fresh attempt must not re-import it.
    with pytest.raises(ImportError_):
        _make_importer().import_job(posting_id)
    assert len(db.list_applications()) == 0


# ── Failure safety ───────────────────────────────────────────────────────────

def test_import_failure_leaves_no_broken_application(temp_db, temp_apps_dir, master_cv, monkeypatch):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    def boom(app_id, company, role):
        raise OSError("disk full simulation")

    monkeypatch.setattr("cv_optimizer.discovery.importer._build_app_dir", boom)

    with pytest.raises(OSError):
        _make_importer().import_job(posting_id)

    # DB rolled back: no application row, posting still retryable.
    assert len(db.list_applications()) == 0
    job = db.get_job_posting(posting_id)
    assert job["application_id"] is None
    assert job["user_state"] == "pending"
    # No stray directories for applications that don't exist.
    assert len(list(Path(temp_apps_dir).glob("*"))) == 0


def test_jd_file_failure_cleans_directory(temp_db, temp_apps_dir, master_cv, monkeypatch):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    real_write = Path.write_text

    def failing_write(self, *args, **kwargs):
        if self.name == "job_description.md":
            raise OSError("disk full simulation")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)

    with pytest.raises(OSError):
        _make_importer().import_job(posting_id)

    assert len(db.list_applications()) == 0
    assert len(list(Path(temp_apps_dir).glob("*"))) == 0
    job = db.get_job_posting(posting_id)
    assert job["user_state"] == "pending"


# ── JD file format ───────────────────────────────────────────────────────────

def test_jd_file_has_metadata_header(temp_db, temp_apps_dir, master_cv):
    posting_id = _insert_posting()
    db.set_job_prefilter(posting_id, "pass", None)
    _insert_assessment(posting_id, score=94)

    result = _make_importer().import_job(posting_id)
    app = db.get_application(result["application_id"])
    content = Path(app[3]).read_text(encoding="utf-8")
    assert content.startswith("# Senior Frontend Engineer")
    assert "Company: Dash0" in content
    assert "---" in content
    assert "React and TypeScript" in content
