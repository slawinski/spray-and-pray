import json
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("applications.db")


def _connect() -> sqlite3.Connection:
    """Returns a configured connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Creates tables if they don't already exist."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id         INTEGER PRIMARY KEY,
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
            """
        )
    try:
        conn.execute("ALTER TABLE applications ADD COLUMN job_url TEXT")
    except Exception:
        pass
    logger.info("Database initialised at %s", DB_PATH)


def insert_application(
    company: str,
    role: str,
    jd_path: str = None,
    cv_path: str = None,
    job_url: str = None,
) -> int:
    """Inserts a new application and returns its id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO applications (company, role, jd_path, cv_path, job_url) VALUES (?, ?, ?, ?, ?)",
            (company, role, jd_path, cv_path, job_url),
        )
        new_id = cursor.lastrowid
    logger.info("Inserted application %d — %s @ %s", new_id, role, company)
    return new_id


def insert_status(application_id: int, status: str) -> None:
    """Records a status transition for an application."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO status_history (application_id, status) VALUES (?, ?)",
            (application_id, status),
        )
    logger.info("Application %d → %s", application_id, status)


def get_all_transitions() -> list[tuple[int, str, str]]:
    """Returns all (application_id, status, transitioned_at) ordered by application_id, transitioned_at ASC."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT application_id, status, transitioned_at "
            "FROM status_history "
            "ORDER BY application_id, transitioned_at ASC"
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


def find_application(company: str, role: str) -> dict | None:
    """Return the first application matching company+role (case-insensitive), or None."""
    init_db()
    for app in list_applications_with_status():
        if app["company"].lower() == company.lower() and app["role"].lower() == role.lower():
            return app
    return None


def list_applications_with_status() -> list[dict]:
    """Return all apps with their latest status and full history."""
    init_db()
    apps = list_applications()
    result = []
    with _connect() as conn:
        for app in apps:
            app_id, company, role, jd_path, cv_path, created_at, job_url = app
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
                "job_url": job_url,
                "created_at": created_at,
                "latest_status": latest_status,
                "history": history,
            })
    return result


def update_application(
    application_id: int,
    jd_path: str = None,
    cv_path: str = None,
) -> None:
    """Updates jd_path and/or cv_path on an existing application."""
    init_db()
    fields: list[str] = []
    values: list[str] = []

    if jd_path is not None:
        fields.append("jd_path = ?")
        values.append(jd_path)
    if cv_path is not None:
        fields.append("cv_path = ?")
        values.append(cv_path)

    if not fields:
        return

    values.append(application_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE applications SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
    logger.info("Updated application %d", application_id)


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
