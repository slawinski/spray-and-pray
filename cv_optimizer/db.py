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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS status_history (
                id              INTEGER PRIMARY KEY,
                application_id  INTEGER NOT NULL,
                status          TEXT NOT NULL,
                transitioned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            );
            """
        )
    logger.info("Database initialised at %s", DB_PATH)


def insert_application(
    company: str,
    role: str,
    jd_path: str = None,
    cv_path: str = None,
) -> int:
    """Inserts a new application and returns its id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO applications (company, role, jd_path, cv_path) VALUES (?, ?, ?, ?)",
            (company, role, jd_path, cv_path),
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


def list_applications_with_status() -> list[dict]:
    """Return all apps with their latest status and full history."""
    init_db()
    apps = list_applications()
    result = []
    with _connect() as conn:
        for app in apps:
            app_id, company, role, jd_path, cv_path, created_at = app
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
