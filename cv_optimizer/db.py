import json
import re
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("applications.db")

_INTERVIEW_PATTERN = re.compile(r"^interview (\d+)$")


def status_rank(status: str) -> int:
    """Returns a numeric rank for a status, used to detect backward transitions.

    This is the canonical source of truth. Keep in sync with the SQL CASE in
    `trg_status_forward_only` (see init_db).
    """
    if status == "draft":
        return -1
    if status == "applied":
        return 0
    if status == "ghosted":
        return 1
    m = _INTERVIEW_PATTERN.match(status)
    if m:
        return 2 + int(m.group(1))
    if status == "offer":
        return 97
    if status == "accepted":
        return 98
    if status == "rejected":
        return 99
    if status == "withdrawn":
        return 99
    return 100  # unknown — always forward


def _connect() -> sqlite3.Connection:
    """Returns a configured connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def connect() -> sqlite3.Connection:
    """Public access to a configured connection for multi-step transactions."""
    return _connect()


def init_db() -> None:
    """Creates tables if they don't already exist."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                company    TEXT NOT NULL,
                role       TEXT NOT NULL,
                jd_path    TEXT,
                cv_path    TEXT,
                job_url    TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS status_history (
                id              INTEGER PRIMARY KEY,
                application_id  INTEGER NOT NULL,
                status          TEXT NOT NULL,
                transitioned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            );

            CREATE TABLE IF NOT EXISTS interview_sessions (
                id              INTEGER PRIMARY KEY,
                application_id  INTEGER NOT NULL,
                questions_json  TEXT NOT NULL,
                answers_json    TEXT,
                scores_json     TEXT,
                readiness_score INTEGER,
                report_text     TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at    DATETIME,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id              INTEGER PRIMARY KEY,
                session_id      INTEGER,
                application_id  INTEGER,
                concept         TEXT NOT NULL,
                content_json    TEXT NOT NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                parent_lesson_id INTEGER,
                FOREIGN KEY (session_id) REFERENCES interview_sessions(id),
                FOREIGN KEY (application_id) REFERENCES applications(id)
            );

            CREATE TABLE IF NOT EXISTS match_assessments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id      INTEGER NOT NULL,
                score               INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                label               TEXT NOT NULL,
                confidence          TEXT NOT NULL,
                base_score          REAL NOT NULL,
                assessment_json     TEXT NOT NULL,
                candidate_hash      TEXT NOT NULL,
                jd_hash             TEXT NOT NULL,
                scoring_version     TEXT NOT NULL,
                prompt_version      TEXT NOT NULL,
                model_name          TEXT NOT NULL,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_match_assessments_app
            ON match_assessments(application_id, id DESC);

            CREATE TABLE IF NOT EXISTS job_postings (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,

                company             TEXT NOT NULL,
                role                TEXT NOT NULL,
                description         TEXT NOT NULL,
                description_hash    TEXT NOT NULL,

                canonical_url       TEXT,

                location_text       TEXT,
                work_model          TEXT NOT NULL DEFAULT 'unknown',
                remote_scope        TEXT NOT NULL DEFAULT 'unknown',
                seniority           TEXT NOT NULL DEFAULT 'unknown',
                employment_type     TEXT,

                salary_min          REAL,
                salary_max          REAL,
                salary_currency     TEXT,
                salary_period       TEXT,
                salary_raw          TEXT,

                posted_at           DATETIME,
                first_seen_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                active_state        TEXT NOT NULL DEFAULT 'unknown',
                active_confidence   TEXT NOT NULL DEFAULT 'low',

                prefilter_state     TEXT NOT NULL DEFAULT 'pending',
                prefilter_reason    TEXT,

                match_state         TEXT NOT NULL DEFAULT 'pending',
                latest_match_score  INTEGER,
                latest_match_label  TEXT,

                user_state          TEXT NOT NULL DEFAULT 'pending',

                application_id      INTEGER UNIQUE,
                imported_at         DATETIME,
                dismissed_at        DATETIME,

                -- normalized L3 dedupe fingerprint components (indexed)
                company_norm        TEXT,
                role_norm           TEXT,
                location_norm       TEXT,

                -- consecutive poll absences for direct ATS feeds
                consecutive_absences INTEGER NOT NULL DEFAULT 0,

                FOREIGN KEY(application_id)
                    REFERENCES applications(id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_job_postings_canonical_url
            ON job_postings(canonical_url);

            CREATE INDEX IF NOT EXISTS idx_job_postings_fingerprint
            ON job_postings(company_norm, role_norm, location_norm);

            CREATE INDEX IF NOT EXISTS idx_job_postings_application
            ON job_postings(application_id);

            CREATE TABLE IF NOT EXISTS job_source_refs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_posting_id  INTEGER NOT NULL,

                source          TEXT NOT NULL,
                external_id     TEXT NOT NULL,

                source_url      TEXT,
                apply_url       TEXT,

                raw_json        TEXT,

                first_seen_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                active_state    TEXT NOT NULL DEFAULT 'unknown',

                FOREIGN KEY(job_posting_id)
                    REFERENCES job_postings(id)
                    ON DELETE CASCADE,

                UNIQUE(source, external_id)
            );

            CREATE INDEX IF NOT EXISTS idx_job_source_refs_job
            ON job_source_refs(job_posting_id);

            CREATE TABLE IF NOT EXISTS job_match_assessments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                job_posting_id      INTEGER NOT NULL,

                score               INTEGER NOT NULL
                                    CHECK(score >= 0 AND score <= 100),

                label               TEXT NOT NULL,
                confidence          TEXT NOT NULL,
                base_score          REAL NOT NULL,

                assessment_json     TEXT NOT NULL,

                candidate_hash      TEXT NOT NULL,
                jd_hash             TEXT NOT NULL,

                scoring_version     TEXT NOT NULL,
                prompt_version      TEXT NOT NULL,
                model_name          TEXT NOT NULL,

                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(job_posting_id)
                    REFERENCES job_postings(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_job_match_job
            ON job_match_assessments(job_posting_id, id DESC);

            CREATE INDEX IF NOT EXISTS idx_job_match_cache
            ON job_match_assessments(
                job_posting_id,
                candidate_hash,
                jd_hash,
                scoring_version,
                prompt_version,
                model_name
            );

            CREATE TABLE IF NOT EXISTS discovery_runs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at        DATETIME,

                status              TEXT NOT NULL DEFAULT 'running',

                fetched_count       INTEGER NOT NULL DEFAULT 0,
                normalized_count    INTEGER NOT NULL DEFAULT 0,
                new_count           INTEGER NOT NULL DEFAULT 0,
                updated_count       INTEGER NOT NULL DEFAULT 0,
                filtered_count      INTEGER NOT NULL DEFAULT 0,
                scored_count        INTEGER NOT NULL DEFAULT 0,
                qualified_count     INTEGER NOT NULL DEFAULT 0,
                imported_count      INTEGER NOT NULL DEFAULT 0,

                source_stats_json   TEXT,
                errors_json         TEXT
            );
            """
        )
        try:
            conn.execute("ALTER TABLE applications ADD COLUMN job_url TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE applications ADD COLUMN source TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE lessons ADD COLUMN parent_lesson_id INTEGER")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE applications ADD COLUMN cover_letter_path TEXT")
        except Exception:
            pass
        # Block backward status transitions at the storage layer, so even raw
        # SQL cannot reintroduce a circular (draft -> applied -> draft) relation.
        # Rank values must stay in sync with status_rank() above.
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_status_forward_only
            BEFORE INSERT ON status_history
            FOR EACH ROW
            WHEN (
                (CASE
                    WHEN NEW.status = 'draft' THEN -1
                    WHEN NEW.status = 'applied' THEN 0
                    WHEN NEW.status = 'ghosted' THEN 1
                    WHEN NEW.status = 'offer' THEN 97
                    WHEN NEW.status = 'accepted' THEN 98
                    WHEN NEW.status = 'rejected' THEN 99
                    WHEN NEW.status = 'withdrawn' THEN 99
                    WHEN NEW.status LIKE 'interview %' THEN 2 + CAST(substr(NEW.status, 11) AS INTEGER)
                    ELSE 100 END)
                <
                (SELECT MAX(CASE
                    WHEN status = 'draft' THEN -1
                    WHEN status = 'applied' THEN 0
                    WHEN status = 'ghosted' THEN 1
                    WHEN status = 'offer' THEN 97
                    WHEN status = 'accepted' THEN 98
                    WHEN status = 'rejected' THEN 99
                    WHEN status = 'withdrawn' THEN 99
                    WHEN status LIKE 'interview %' THEN 2 + CAST(substr(status, 11) AS INTEGER)
                    ELSE 100 END)
                FROM status_history WHERE application_id = NEW.application_id)
            )
            BEGIN
                SELECT RAISE(ABORT, 'backward status transition blocked');
            END;
            """
        )
    _migrate_autoincrement()
    logger.info("Database initialised at %s", DB_PATH)


def _migrate_autoincrement() -> None:
    """Migrate existing applications table to use AUTOINCREMENT if it doesn't already."""
    with _connect() as conn:
        table_info = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='applications'"
        ).fetchone()
    if not table_info:
        return
    if "AUTOINCREMENT" in table_info[0].upper():
        return

    logger.info("Migrating applications table to AUTOINCREMENT...")
    with _connect() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(
            """
            CREATE TABLE applications_new (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                company    TEXT NOT NULL,
                role       TEXT NOT NULL,
                jd_path    TEXT,
                cv_path    TEXT,
                job_url    TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source     TEXT,
                cover_letter_path TEXT
            );
            INSERT INTO applications_new (id, company, role, jd_path, cv_path, job_url, created_at, source, cover_letter_path)
                SELECT id, company, role, jd_path, cv_path, job_url, created_at, source, cover_letter_path FROM applications;
            DROP TABLE applications;
            ALTER TABLE applications_new RENAME TO applications;
            """
        )
        conn.execute("PRAGMA foreign_keys=ON")
    logger.info("AUTOINCREMENT migration complete")


def insert_application(
    company: str,
    role: str,
    jd_path: str = None,
    cv_path: str = None,
    job_url: str = None,
    source: str = None,
) -> int:
    """Inserts a new application and returns its id.

    `source` identifies the ingestion channel (e.g. 'direct', 'recruiter',
    'auto:serpapi'). It participates in duplicate detection and is shown in
    the TUI, so it MUST be persisted.
    """
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO applications (company, role, jd_path, cv_path, job_url, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (company, role, jd_path, cv_path, job_url, source),
        )
        new_id = cursor.lastrowid
    logger.info("Inserted application %d — %s @ %s (source=%s)", new_id, role, company, source)
    return new_id


def insert_status(application_id: int, status: str) -> None:
    """Records a status transition for an application.

    Raises ValueError if the transition is backward (lower rank than the
    current latest status), which would create a circular Sankey relation.
    """
    init_db()
    new_rank = status_rank(status)
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM status_history "
            "WHERE application_id = ? ORDER BY transitioned_at DESC, id DESC LIMIT 1",
            (application_id,),
        ).fetchone()
        if row is not None and status_rank(row[0]) > new_rank:
            raise ValueError(
                f"Backward status transition blocked: {row[0]} → {status}. "
                "Use update_status() to revert cleanly."
            )
        conn.execute(
            "INSERT INTO status_history (application_id, status) VALUES (?, ?)",
            (application_id, status),
        )
    logger.info("Application %d → %s", application_id, status)


def get_latest_status(application_id: int) -> str | None:
    """Return the most recent status for an application, or None."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM status_history "
            "WHERE application_id = ? "
            "ORDER BY transitioned_at DESC, id DESC LIMIT 1",
            (application_id,),
        ).fetchone()
    return row[0] if row else None


def get_status_history_with_ids(application_id: int) -> list[tuple[int, str, str]]:
    """Returns all (id, status, transitioned_at) for one application, ordered ASC."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, status, transitioned_at FROM status_history "
            "WHERE application_id = ? ORDER BY transitioned_at ASC, id ASC",
            (application_id,),
        ).fetchall()
    return rows


def delete_status_by_id(status_id: int) -> None:
    """Deletes a single status_history row by its id."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM status_history WHERE id = ?", (status_id,))
    logger.info("Deleted status_history row %d", status_id)


def get_all_transitions() -> list[tuple[int, str, str]]:
    """Returns all (application_id, status, transitioned_at) ordered by application_id, transitioned_at ASC."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT application_id, status, transitioned_at "
            "FROM status_history "
            "ORDER BY application_id, transitioned_at ASC, id ASC"
        ).fetchall()
    return rows


def get_application(application_id: int) -> tuple | None:
    """Returns a single application row or None."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
    return row


def list_applications() -> list[tuple]:
    """Returns all applications ordered by created_at DESC."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM applications ORDER BY created_at DESC"
        ).fetchall()
    return rows


def _normalize_source(source: str | None) -> str:
    """Canonicalizes a source channel; empty/None means 'direct'."""
    s = (source or "").strip().lower()
    return s or "direct"


def find_application(company: str, role: str, source: str | None = None) -> dict | None:
    """Return the first application matching company+role (case-insensitive) AND
    source channel, or None.

    Two applications for the same company+role are only duplicates when they
    also share the same source channel (e.g. 'recruiter' vs 'direct'). This
    lets you track the same role through a recruiter and again directly.
    """
    init_db()
    target_source = _normalize_source(source)
    for app in list_applications_with_status():
        if (
            app["company"].lower() == company.lower()
            and app["role"].lower() == role.lower()
            and _normalize_source(app.get("source")) == target_source
        ):
            return app
    return None


def list_applications_with_status() -> list[dict]:
    """Return all apps with their latest status and full history."""
    init_db()
    apps = list_applications()
    result = []
    with _connect() as conn:
        for app in apps:
            app_id, company, role, jd_path, cv_path, job_url, created_at, source, cover_letter_path = app
            history_rows = conn.execute(
                "SELECT status, transitioned_at FROM status_history "
                "WHERE application_id = ? ORDER BY transitioned_at ASC",
                (app_id,),
            ).fetchall()
            history = [{"status": r[0], "transitioned_at": r[1]} for r in history_rows]
            latest_status = history[-1]["status"] if history else "unknown"
            result.append({
                "id": app_id,
                "company": company,
                "role": role,
                "jd_path": jd_path,
                "cv_path": cv_path,
                "cover_letter_path": cover_letter_path,
                "job_url": job_url,
                "source": source,
                "created_at": created_at,
                "latest_status": latest_status,
                "history": history,
            })
    return result


def delete_application(application_id: int) -> None:
    """Deletes an application and all related records (status_history, interview_sessions, lessons)."""
    init_db()
    with _connect() as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM lessons WHERE application_id = ?", (application_id,))
        conn.execute("DELETE FROM interview_sessions WHERE application_id = ?", (application_id,))
        conn.execute("DELETE FROM status_history WHERE application_id = ?", (application_id,))
        conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
    logger.info("Deleted application %d and all related records", application_id)


def update_application(
    application_id: int,
    jd_path: str = None,
    cv_path: str = None,
    cover_letter_path: str = None,
) -> None:
    """Updates jd_path, cv_path, and/or cover_letter_path on an existing application."""
    init_db()
    fields: list[str] = []
    values: list[str] = []

    if jd_path is not None:
        fields.append("jd_path = ?")
        values.append(jd_path)
    if cv_path is not None:
        fields.append("cv_path = ?")
        values.append(cv_path)
    if cover_letter_path is not None:
        fields.append("cover_letter_path = ?")
        values.append(cover_letter_path)

    if not fields:
        return

    values.append(application_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE applications SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
    logger.info("Updated application %d", application_id)


def set_source(application_id: int, source: str | None) -> None:
    """Sets or clears the source override for an application."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET source = ? WHERE id = ?",
            (source, application_id),
        )
    logger.info("Set source for app %d to %s", application_id, source)


def set_application_job_url(application_id: int, job_url: str | None) -> None:
    """Sets or clears the job posting URL for an application."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE applications SET job_url = ? WHERE id = ?",
            (job_url, application_id),
        )
    logger.info("Set job_url for app %d to %s", application_id, job_url)


def create_interview_session(application_id: int, questions: list[dict]) -> int:
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO interview_sessions (application_id, questions_json) VALUES (?, ?)",
            (application_id, json.dumps(questions)),
        )
        return cursor.lastrowid


def get_interview_session(session_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "application_id": row[1],
        "questions_json": row[2],
        "answers_json": row[3],
        "scores_json": row[4],
        "readiness_score": row[5],
        "report_text": row[6],
        "created_at": row[7],
        "completed_at": row[8],
    }


def save_interview_answer(session_id: int, answers_json: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE interview_sessions SET answers_json = ? WHERE id = ?",
            (answers_json, session_id),
        )


def complete_interview_session(
    session_id: int,
    scores_json: str,
    readiness_score: int,
    report_text: str,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE interview_sessions SET scores_json = ?, readiness_score = ?, report_text = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (scores_json, readiness_score, report_text, session_id),
        )


def get_in_progress_session(app_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE application_id = ? AND completed_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (app_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "application_id": row[1],
        "questions_json": row[2],
        "answers_json": row[3],
        "scores_json": row[4],
        "readiness_score": row[5],
        "report_text": row[6],
        "created_at": row[7],
        "completed_at": row[8],
    }


def get_latest_readiness(app_id: int) -> int | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT readiness_score FROM interview_sessions WHERE application_id = ? AND readiness_score IS NOT NULL ORDER BY created_at DESC LIMIT 1",
            (app_id,),
        ).fetchone()
    return row[0] if row else None


def get_latest_readiness_batch(application_ids: list[int]) -> dict[int, int]:
    """Batch-loads the latest readiness score per application id (no N+1)."""
    if not application_ids:
        return {}
    init_db()
    placeholders = ",".join("?" for _ in application_ids)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT application_id, readiness_score FROM interview_sessions "
            f"WHERE application_id IN ({placeholders}) "
            f"AND readiness_score IS NOT NULL "
            f"ORDER BY created_at DESC, id DESC",
            tuple(application_ids),
        ).fetchall()
    result: dict[int, int] = {}
    for app_id, score in rows:
        if app_id not in result:
            result[app_id] = score
    return result


def create_lesson(
    concept: str,
    content_json: str,
    session_id: int | None = None,
    app_id: int | None = None,
    parent_lesson_id: int | None = None,
) -> int:
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO lessons (concept, content_json, session_id, application_id, parent_lesson_id) VALUES (?, ?, ?, ?, ?)",
            (concept, content_json, session_id, app_id, parent_lesson_id),
        )
        return cursor.lastrowid


def get_lesson(lesson_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM lessons WHERE id = ?",
            (lesson_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "session_id": row[1],
        "application_id": row[2],
        "concept": row[3],
        "content_json": row[4],
        "created_at": row[5],
        "parent_lesson_id": row[6],
    }


def get_parent_lesson(lesson_id: int) -> dict | None:
    """Return the parent lesson info (id, title) for a given lesson, or None."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT p.id, p.concept, p.content_json FROM lessons c "
            "JOIN lessons p ON c.parent_lesson_id = p.id "
            "WHERE c.id = ?", (lesson_id,)
        ).fetchone()
    if not row:
        return None
    content = json.loads(row[2])
    return {
        "id": row[0],
        "title": content.get("title", row[1]),
    }


def list_lessons() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM lessons ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": row[0],
            "session_id": row[1],
            "application_id": row[2],
            "concept": row[3],
            "content_json": row[4],
            "created_at": row[5],
            "parent_lesson_id": row[6],
        }
        for row in rows
    ]


def find_lesson_by_concept(concept: str, app_id: int | None = None) -> dict | None:
    init_db()
    with _connect() as conn:
        if app_id is not None:
            row = conn.execute(
                "SELECT * FROM lessons WHERE concept = ? AND application_id = ? ORDER BY created_at DESC LIMIT 1",
                (concept, app_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM lessons WHERE concept = ? ORDER BY created_at DESC LIMIT 1",
                (concept,),
            ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "session_id": row[1],
        "application_id": row[2],
        "concept": row[3],
        "content_json": row[4],
        "created_at": row[5],
        "parent_lesson_id": row[6],
    }


# ═══════════════════════════════════════════════════════════════
# Match assessments
# ═══════════════════════════════════════════════════════════════

def insert_match_assessment(
    application_id: int,
    score: int,
    label: str,
    confidence: str,
    base_score: float,
    assessment_json: str,
    candidate_hash: str,
    jd_hash: str,
    scoring_version: str,
    prompt_version: str,
    model_name: str,
) -> int:
    """Inserts a match assessment row and returns its id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO match_assessments "
            "(application_id, score, label, confidence, base_score, assessment_json, "
            " candidate_hash, jd_hash, scoring_version, prompt_version, model_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (application_id, score, label, confidence, base_score, assessment_json,
             candidate_hash, jd_hash, scoring_version, prompt_version, model_name),
        )
        return cursor.lastrowid


def get_latest_match(application_id: int) -> dict | None:
    """Returns the most recent match assessment for an application, or None."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM match_assessments WHERE application_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (application_id,),
        ).fetchone()
    return dict(row) if row else None


def get_latest_matches(application_ids: list[int]) -> dict[int, dict]:
    """Batch-loads the latest match assessment per application id."""
    if not application_ids:
        return {}
    init_db()
    placeholders = ",".join("?" for _ in application_ids)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM match_assessments WHERE application_id IN ({placeholders}) "
            "ORDER BY id DESC",
            tuple(application_ids),
        ).fetchall()
    result: dict[int, dict] = {}
    for row in rows:
        r = dict(row)
        app_id = r["application_id"]
        if app_id not in result:
            result[app_id] = r
    return result


def find_cached_match(
    application_id: int,
    candidate_hash: str,
    jd_hash: str,
    scoring_version: str,
    prompt_version: str,
    model_name: str,
) -> dict | None:
    """Returns a cached assessment matching all identity fingerprints, or None."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM match_assessments WHERE application_id = ? "
            "AND candidate_hash = ? AND jd_hash = ? AND scoring_version = ? "
            "AND prompt_version = ? AND model_name = ? "
            "ORDER BY id DESC LIMIT 1",
            (application_id, candidate_hash, jd_hash, scoring_version, prompt_version, model_name),
        ).fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════
# Discovery persistence — job_postings / job_source_refs /
# job_match_assessments / discovery_runs
# ═══════════════════════════════════════════════════════════════

def _job_row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def insert_job_posting(
    company: str,
    role: str,
    description: str,
    description_hash: str,
    canonical_url: str | None = None,
    location_text: str | None = None,
    work_model: str = "unknown",
    remote_scope: str = "unknown",
    seniority: str = "unknown",
    employment_type: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    salary_currency: str | None = None,
    salary_period: str | None = None,
    salary_raw: str | None = None,
    posted_at: str | None = None,
    active_state: str = "unknown",
    active_confidence: str = "low",
    company_norm: str | None = None,
    role_norm: str | None = None,
    location_norm: str | None = None,
) -> int:
    """Inserts a canonical job posting and returns its id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO job_postings ("
            " company, role, description, description_hash, canonical_url,"
            " location_text, work_model, remote_scope, seniority, employment_type,"
            " salary_min, salary_max, salary_currency, salary_period, salary_raw,"
            " posted_at, active_state, active_confidence,"
            " company_norm, role_norm, location_norm"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (company, role, description, description_hash, canonical_url,
             location_text, work_model, remote_scope, seniority, employment_type,
             salary_min, salary_max, salary_currency, salary_period, salary_raw,
             posted_at, active_state, active_confidence,
             company_norm, role_norm, location_norm),
        )
        return cursor.lastrowid


def get_job_posting(job_posting_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM job_postings WHERE id = ?", (job_posting_id,)
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def get_job_posting_by_canonical_url(canonical_url: str) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM job_postings WHERE canonical_url = ? "
            "ORDER BY id DESC LIMIT 1",
            (canonical_url,),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def get_job_posting_by_source_id(source: str, external_id: str) -> dict | None:
    """Returns the canonical posting owning a (source, external_id) ref."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT p.* FROM job_postings p "
            "JOIN job_source_refs r ON r.job_posting_id = p.id "
            "WHERE r.source = ? AND r.external_id = ? "
            "ORDER BY p.id DESC LIMIT 1",
            (source, external_id),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def find_job_postings_by_fingerprint(
    company_norm: str, role_norm: str, location_norm: str
) -> list[dict]:
    """L3 dedupe candidates: same normalized company/title/location."""
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM job_postings WHERE company_norm = ? AND role_norm = ? "
            "AND location_norm = ?",
            (company_norm, role_norm, location_norm),
        ).fetchall()
    return [_job_row_to_dict(r) for r in rows]


def get_job_posting_by_application(application_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM job_postings WHERE application_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (application_id,),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def get_job_postings_by_application_ids(application_ids: list[int]) -> dict[int, dict]:
    """Batch lookup of discovery metadata keyed by application id."""
    if not application_ids:
        return {}
    init_db()
    placeholders = ",".join("?" for _ in application_ids)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM job_postings WHERE application_id IN ({placeholders})",
            tuple(application_ids),
        ).fetchall()
    return {r["application_id"]: _job_row_to_dict(r) for r in rows}


def update_job_posting_seen(
    job_posting_id: int,
    *,
    description: str | None = None,
    description_hash: str | None = None,
    canonical_url: str | None = None,
    active_state: str | None = None,
    active_confidence: str | None = None,
    consecutive_absences: int | None = None,
    reset_match: bool = False,
) -> None:
    """Updates staleness/activity fields after a posting is seen again."""
    init_db()
    fields = ["last_seen_at = CURRENT_TIMESTAMP"]
    values: list = []
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if description_hash is not None:
        fields.append("description_hash = ?")
        values.append(description_hash)
    if canonical_url is not None:
        fields.append("canonical_url = ?")
        values.append(canonical_url)
    if active_state is not None:
        fields.append("active_state = ?")
        values.append(active_state)
    if active_confidence is not None:
        fields.append("active_confidence = ?")
        values.append(active_confidence)
    if consecutive_absences is not None:
        fields.append("consecutive_absences = ?")
        values.append(consecutive_absences)
    if reset_match:
        fields.append("match_state = 'pending'")
    values.append(job_posting_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE job_postings SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )


def get_pending_import_jobs(limit: int = 200) -> list[dict]:
    """Scored, un-imported, non-dismissed, active postings awaiting import.

    Used by the orchestrator to import previously scored qualifying jobs
    without re-fetching or re-scoring them.
    """
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM job_postings WHERE match_state = 'scored' "
            "AND user_state = 'pending' AND application_id IS NULL "
            "AND active_state != 'inactive' AND prefilter_state != 'fail' "
            "AND latest_match_score IS NOT NULL "
            "ORDER BY latest_match_score DESC, last_seen_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_job_row_to_dict(r) for r in rows]


def bump_job_posting_absence(job_posting_id: int) -> int:
    """Increments the consecutive-absence counter; returns the new value."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE job_postings SET consecutive_absences = consecutive_absences + 1 "
            "WHERE id = ?",
            (job_posting_id,),
        )
        row = conn.execute(
            "SELECT consecutive_absences FROM job_postings WHERE id = ?",
            (job_posting_id,),
        ).fetchone()
    return row[0] if row else 0


def set_job_prefilter(job_posting_id: int, state: str, reason: str | None) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE job_postings SET prefilter_state = ?, prefilter_reason = ? "
            "WHERE id = ?",
            (state, reason, job_posting_id),
        )


def set_job_match_state(job_posting_id: int, match_state: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE job_postings SET match_state = ? WHERE id = ?",
            (match_state, job_posting_id),
        )


def set_job_latest_match(
    job_posting_id: int,
    *,
    score: int,
    label: str,
    match_state: str,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE job_postings SET latest_match_score = ?, latest_match_label = ?, "
            "match_state = ? WHERE id = ?",
            (score, label, match_state, job_posting_id),
        )


def set_job_user_state(
    job_posting_id: int,
    user_state: str,
    *,
    dismissed_at: str | None = None,
) -> None:
    init_db()
    with _connect() as conn:
        if dismissed_at is None and user_state == "dismissed":
            conn.execute(
                "UPDATE job_postings SET user_state = ?, dismissed_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (user_state, job_posting_id),
            )
        else:
            conn.execute(
                "UPDATE job_postings SET user_state = ?, dismissed_at = ? WHERE id = ?",
                (user_state, dismissed_at, job_posting_id),
            )


def link_job_to_application(
    job_posting_id: int, application_id: int
) -> None:
    """Marks a job posting as imported and linked to an application."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE job_postings SET application_id = ?, user_state = 'imported', "
            "imported_at = CURRENT_TIMESTAMP WHERE id = ?",
            (application_id, job_posting_id),
        )


def dismiss_job_for_application(application_id: int) -> None:
    """Marks any posting linked to an application as dismissed.

    Used when the user deletes an auto-imported Draft: the discovery record
    survives (application_id becomes NULL via FK) and prevents re-import.
    """
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE job_postings SET user_state = 'dismissed', "
            "dismissed_at = CURRENT_TIMESTAMP WHERE application_id = ?",
            (application_id,),
        )


def insert_job_source_ref(
    job_posting_id: int,
    source: str,
    external_id: str,
    *,
    source_url: str | None = None,
    apply_url: str | None = None,
    raw_json: str | None = None,
    active_state: str = "unknown",
) -> int:
    """Upserts a source ref. Returns the ref id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO job_source_refs "
            "(job_posting_id, source, external_id, source_url, apply_url, raw_json, active_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(source, external_id) DO UPDATE SET "
            "last_seen_at = CURRENT_TIMESTAMP, source_url = COALESCE(excluded.source_url, job_source_refs.source_url), "
            "apply_url = COALESCE(excluded.apply_url, job_source_refs.apply_url), "
            "raw_json = COALESCE(excluded.raw_json, job_source_refs.raw_json), "
            "active_state = excluded.active_state",
            (job_posting_id, source, external_id, source_url, apply_url, raw_json, active_state),
        )
        row = conn.execute(
            "SELECT id FROM job_source_refs WHERE source = ? AND external_id = ?",
            (source, external_id),
        ).fetchone()
    return row[0] if row else 0


def get_job_source_refs(job_posting_id: int) -> list[dict]:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM job_source_refs WHERE job_posting_id = ? ORDER BY id",
            (job_posting_id,),
        ).fetchall()
    return [_job_row_to_dict(r) for r in rows]


def insert_job_match_assessment(
    job_posting_id: int,
    score: int,
    label: str,
    confidence: str,
    base_score: float,
    assessment_json: str,
    candidate_hash: str,
    jd_hash: str,
    scoring_version: str,
    prompt_version: str,
    model_name: str,
) -> int:
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO job_match_assessments "
            "(job_posting_id, score, label, confidence, base_score, assessment_json, "
            " candidate_hash, jd_hash, scoring_version, prompt_version, model_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_posting_id, score, label, confidence, base_score, assessment_json,
             candidate_hash, jd_hash, scoring_version, prompt_version, model_name),
        )
        return cursor.lastrowid


def get_latest_job_match(job_posting_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM job_match_assessments WHERE job_posting_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (job_posting_id,),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def find_cached_job_match(
    job_posting_id: int,
    candidate_hash: str,
    jd_hash: str,
    scoring_version: str,
    prompt_version: str,
    model_name: str,
) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM job_match_assessments WHERE job_posting_id = ? "
            "AND candidate_hash = ? AND jd_hash = ? AND scoring_version = ? "
            "AND prompt_version = ? AND model_name = ? "
            "ORDER BY id DESC LIMIT 1",
            (job_posting_id, candidate_hash, jd_hash, scoring_version, prompt_version, model_name),
        ).fetchone()
    return _job_row_to_dict(row) if row else None


def create_discovery_run() -> int:
    init_db()
    with _connect() as conn:
        # The lock prevents concurrent runs, so any row still 'running'
        # belongs to a crashed process — close it out before starting fresh.
        conn.execute(
            "UPDATE discovery_runs SET status = 'failed', "
            "completed_at = CURRENT_TIMESTAMP WHERE status = 'running'"
        )
        cursor = conn.execute(
            "INSERT INTO discovery_runs (status) VALUES ('running')"
        )
        return cursor.lastrowid


def update_discovery_run(run_id: int, **counts: int) -> None:
    init_db()
    allowed = {
        "fetched_count", "normalized_count", "new_count", "updated_count",
        "filtered_count", "scored_count", "qualified_count", "imported_count",
    }
    fields = []
    values: list = []
    for key, value in counts.items():
        if key in allowed:
            fields.append(f"{key} = ?")
            values.append(value)
    if not fields:
        return
    values.append(run_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE discovery_runs SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )


def finish_discovery_run(
    run_id: int,
    status: str,
    *,
    source_stats_json: str | None = None,
    errors_json: str | None = None,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE discovery_runs SET status = ?, completed_at = CURRENT_TIMESTAMP, "
            "source_stats_json = ?, errors_json = ? WHERE id = ?",
            (status, source_stats_json, errors_json, run_id),
        )


def get_discovery_run(run_id: int) -> dict | None:
    init_db()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM discovery_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _job_row_to_dict(row) if row else None