"""Application profile storage; synthetic data only, no document generation."""

import sqlite3

import pytest

from cv_optimizer import db


@pytest.mark.parametrize("autoincrement", [False, True])
def test_legacy_backfill_is_once_and_preserves_data(tmp_path, monkeypatch, autoincrement):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    cv = tmp_path / "cv.pdf"
    letter = tmp_path / "letter.pdf"
    cv.write_bytes(b"legacy CV")
    letter.write_bytes(b"legacy letter")
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(f"""CREATE TABLE applications (
            id INTEGER PRIMARY KEY {'AUTOINCREMENT' if autoincrement else ''},
            company TEXT NOT NULL, role TEXT NOT NULL, jd_path TEXT, cv_path TEXT,
            job_url TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT, cover_letter_path TEXT)""")
        conn.execute(
            "INSERT INTO applications (company, role, cv_path, source, cover_letter_path) "
            "VALUES ('Legacy', 'Role', ?, 'recruiter', ?)", (str(cv), str(letter)),
        )
    db.init_db()
    db.insert_status(1, "applied")
    before = db.get_application(1)
    assert len(before) == 9
    assert db.get_application_profile(1) == ("it", 0)
    with db.connect() as conn:
        new_id = conn.execute(
            "INSERT INTO applications (company, role) VALUES ('New', 'Draft')"
        ).lastrowid
    db.init_db()
    db.init_db()
    assert db.get_application_profile(new_id) == (None, 0)
    assert db.get_application(1) == before
    assert before[4] == str(cv) and before[7:] == ("recruiter", str(letter))
    assert db.get_latest_status(1) == "applied"
    assert cv.read_bytes() == b"legacy CV"
    assert letter.read_bytes() == b"legacy letter"


def test_fresh_insert_and_dictionary_metadata(temp_db):
    unselected = db.insert_application("Acme", "Draft")
    selected = db.insert_application("Acme", "Role", cv_profile="mechanical_engineering")
    assert db.get_application_profile(unselected) == (None, 0)
    assert db.get_application_profile(selected) == ("mechanical_engineering", 0)
    assert all(len(row) == 9 for row in db.list_applications())
    apps = {app["id"]: app for app in db.list_applications_with_status()}
    assert apps[unselected]["cv_profile"] is None
    assert apps[selected]["cv_profile"] == "mechanical_engineering"
    assert apps[selected]["cv_profile_revision"] == 0


@pytest.mark.parametrize("profile", ["mechanical_engineering", "baker"])
def test_selection_change_and_same_selection(temp_db, tmp_path, profile):
    cv = tmp_path / "cv.pdf"
    letter = tmp_path / "letter.pdf"
    cv.write_bytes(b"CV")
    letter.write_bytes(b"letter")
    app_id = db.insert_application("Acme", "Role", cv_profile="it", cv_path=str(cv))
    other = db.insert_application("Other", "Role", cv_profile="mechanical_engineering")
    db.update_application(app_id, cover_letter_path=str(letter))
    db.insert_status(app_id, "applied")
    before = db.get_application(app_id)
    assert db.set_application_profile(app_id, "it") == ("it", 0)
    assert db.get_application(app_id) == before
    assert db.set_application_profile(app_id, profile) == (profile, 1)
    assert db.get_application(app_id)[4] is None
    assert db.get_application(app_id)[8] is None
    assert db.set_application_profile(app_id, profile) == (profile, 1)
    db.init_db()
    assert db.get_application_profile(app_id) == (profile, 1)
    assert db.set_application_profile(app_id, "it") == ("it", 2)
    assert db.get_application_profile(other) == ("mechanical_engineering", 0)
    assert db.get_latest_status(app_id) == "applied"
    assert cv.read_bytes() == b"CV" and letter.read_bytes() == b"letter"


def test_select_unselected_and_dedupe_ignores_profile(temp_db):
    app_id = db.insert_application("Acme", "Role", source="direct")
    assert db.set_application_profile(app_id, "it") == ("it", 1)
    assert db.find_application("acme", "role", "direct")["id"] == app_id
    db.set_application_profile(app_id, "mechanical_engineering")
    assert db.find_application("acme", "role", "direct")["id"] == app_id
    assert db.find_application("acme", "role", "recruiter") is None


@pytest.mark.parametrize("profile", ["", "unknown", "IT", 123])
def test_invalid_input_is_rejected_without_mutation(temp_db, profile):
    app_id = db.insert_application("Acme", "Role", cv_profile="it", cv_path="ready.pdf")
    with pytest.raises(ValueError):
        db.insert_application("Bad", "Role", cv_profile=profile)
    with pytest.raises(ValueError):
        db.set_application_profile(app_id, profile)
    assert db.get_application_profile(app_id) == ("it", 0)
    assert db.get_application(app_id)[4] == "ready.pdf"
    assert len(db.list_applications()) == 1


def test_unknown_stored_profile_fails_closed(temp_db):
    app_id = db.insert_application("Acme", "Role")
    with db.connect() as conn:
        conn.execute("UPDATE applications SET cv_profile = 'unknown' WHERE id = ?", (app_id,))
    with pytest.raises(ValueError):
        db.get_application_profile(app_id)
    with pytest.raises(ValueError):
        db.list_applications_with_status()
    with pytest.raises(ValueError):
        db.set_application_profile(app_id, "it")


def test_missing_application_fails_explicitly(temp_db):
    with pytest.raises(ValueError):
        db.get_application_profile(999)
    with pytest.raises(ValueError):
        db.set_application_profile(999, "it")


def test_rebuild_preserves_existing_profile_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "profiled-legacy.db")
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY, company TEXT NOT NULL, role TEXT NOT NULL,
                jd_path TEXT, cv_path TEXT, job_url TEXT, created_at DATETIME,
                cv_profile TEXT, cv_profile_revision INTEGER NOT NULL DEFAULT 0);
            INSERT INTO applications (company, role, cv_profile, cv_profile_revision)
                VALUES ('Selected', 'Role', 'mechanical_engineering', 7);
            INSERT INTO applications (company, role) VALUES ('Unselected', 'Draft');
        """)
    db.init_db()
    db.init_db()
    assert db.get_application_profile(1) == ("mechanical_engineering", 7)
    assert db.get_application_profile(2) == (None, 0)
    assert len(db.get_application(1)) == 9


def test_selection_update_rolls_back_on_storage_failure(temp_db):
    app_id = db.insert_application("Acme", "Role", cv_profile="it", cv_path="ready.pdf")
    db.update_application(app_id, cover_letter_path="letter.pdf")
    with db.connect() as conn:
        conn.executescript("""
            CREATE TRIGGER reject_profile BEFORE UPDATE OF cv_profile ON applications
            BEGIN SELECT RAISE(ABORT, 'test failure'); END;
        """)
    with pytest.raises(sqlite3.IntegrityError):
        db.set_application_profile(app_id, "mechanical_engineering")
    assert db.get_application_profile(app_id) == ("it", 0)
    assert db.get_application(app_id)[4] == "ready.pdf"
    assert db.get_application(app_id)[8] == "letter.pdf"
