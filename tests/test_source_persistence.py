"""Phase 0 regression tests: `source` persistence and applications tuple
layout stability — discovery must not break positional destructuring."""

import sqlite3
from pathlib import Path

from cv_optimizer import db


def test_insert_application_persists_source(temp_db):
    app_id = db.insert_application(
        "Acme", "Frontend Engineer", source="recruiter", job_url="https://acme.example/jobs/1"
    )
    app = db.get_application(app_id)
    assert app[7] == "recruiter"


def test_insert_application_without_source_keeps_null(temp_db):
    app_id = db.insert_application("Acme", "Frontend Engineer")
    app = db.get_application(app_id)
    assert app[7] is None


def test_applications_tuple_layout_unchanged(temp_db):
    """Nine positional columns: id, company, role, jd_path, cv_path,
    job_url, created_at, source, cover_letter_path. Existing destructuring
    (tracker, server, TUI) depends on this exact order."""
    app_id = db.insert_application(
        "Acme", "Frontend Engineer",
        jd_path="a/jd.pdf", cv_path="a/cv.pdf",
        job_url="https://example.com", source="direct",
    )
    app = db.get_application(app_id)
    assert len(app) == 9
    _id, company, role, jd_path, cv_path, job_url, created_at, source, cl_path = app
    assert company == "Acme"
    assert role == "Frontend Engineer"
    assert jd_path == "a/jd.pdf"
    assert cv_path == "a/cv.pdf"
    assert job_url == "https://example.com"
    assert created_at is not None
    assert source == "direct"
    assert cl_path is None


def test_list_applications_with_status_returns_source(temp_db):
    app_id = db.insert_application("Acme", "FE", source="auto:serpapi")
    db.insert_status(app_id, "draft")
    apps = db.list_applications_with_status()
    assert apps[0]["source"] == "auto:serpapi"
    assert apps[0]["latest_status"] == "draft"


def test_find_application_respects_source_channel(temp_db):
    db.insert_application("Acme", "FE", source="direct")
    db.insert_application("Acme", "FE", source="recruiter")
    assert db.find_application("Acme", "FE", source="direct") is not None
    assert db.find_application("Acme", "FE", source="recruiter") is not None
    assert db.find_application("Acme", "FE", source="other") is None


def test_migration_from_existing_database(tmp_path, monkeypatch):
    """init_db() must add discovery tables to an EXISTING database without
    corrupting applications data (migration, not just blank creation)."""
    db_path = tmp_path / "old.db"

    # Build an "old" database the way previous versions did: applications
    # + match_assessments only.
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE applications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company    TEXT NOT NULL,
            role       TEXT NOT NULL,
            jd_path    TEXT,
            cv_path    TEXT,
            job_url    TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE status_history (
            id              INTEGER PRIMARY KEY,
            application_id  INTEGER NOT NULL,
            status          TEXT NOT NULL,
            transitioned_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO applications (company, role, job_url) VALUES ('OldCorp', 'Old Role', 'https://old.example');
        INSERT INTO status_history (application_id, status) VALUES (1, 'draft');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    # Existing data survives.
    apps = db.list_applications_with_status()
    assert len(apps) == 1
    assert apps[0]["company"] == "OldCorp"
    assert apps[0]["source"] is None  # legacy column added as NULL

    # New discovery tables exist and are usable.
    posting_id = db.insert_job_posting(
        company="NewCorp", role="FE", description="x" * 200,
        description_hash="hash", canonical_url="https://new.example",
    )
    assert db.get_job_posting(posting_id)["company"] == "NewCorp"
    db.insert_job_source_ref(posting_id, "serpapi", "ext-1", active_state="active")
    assert db.get_job_posting_by_source_id("serpapi", "ext-1")["id"] == posting_id
    run_id = db.create_discovery_run()
    db.finish_discovery_run(run_id, "completed")
    assert db.get_discovery_run(run_id)["status"] == "completed"


def test_autoincrement_migration_preserves_tuple_order(tmp_path, monkeypatch):
    """The legacy non-AUTOINCREMENT table migration must preserve the exact
    column order: (id, company, role, jd_path, cv_path, job_url, created_at,
    source, cover_letter_path)."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE applications (
            id         INTEGER PRIMARY KEY,
            company    TEXT NOT NULL,
            role       TEXT NOT NULL,
            jd_path    TEXT,
            cv_path    TEXT,
            job_url    TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO applications (company, role) VALUES ('LegacyCo', 'Legacy Role');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()  # triggers _migrate_autoincrement()

    app = db.get_application(1)
    _id, company, role, jd_path, cv_path, job_url, created_at, source, cl_path = app
    assert company == "LegacyCo"
    assert role == "Legacy Role"
    assert job_url is None
    assert created_at is not None
    assert source is None
    assert cl_path is None


def test_stale_running_run_is_closed_on_new_run(temp_db):
    first = db.create_discovery_run()
    second = db.create_discovery_run()
    assert db.get_discovery_run(first)["status"] == "failed"
    assert db.get_discovery_run(second)["status"] == "running"
