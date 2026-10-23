"""Extract one committed SQLite snapshot, including live WAL contents."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cv_optimizer import db

CORE = {'applications': {'id', 'company', 'role'},
        'status_history': {'id', 'application_id', 'status', 'transitioned_at'}}
OPTIONAL = {'match_assessments': {'id', 'application_id', 'created_at', 'assessment_json', 'score'},
            'job_postings': {'id', 'company', 'role'},
            'job_source_refs': {'id', 'job_posting_id'},
            'discovery_runs': {'id', 'status'}}


class ReportLoadError(Exception):
    """Storage cannot provide a valid reporting population; never initialize it."""


def read_snapshot(path=None, *, clock=None):
    path = Path(path if path is not None else db.DB_PATH).resolve()
    conn = None
    try:
        conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN DEFERRED')
        tables, capabilities = {}, {}
        for name, required in (CORE | OPTIONAL).items():
            columns = {r['name'] for r in conn.execute(f'PRAGMA table_info("{name}")')}
            available = required <= columns
            if name in CORE and not available:
                raise ReportLoadError(f'Incompatible core schema: {name}')
            capabilities[name] = available
            tables[name] = [dict(r) for r in conn.execute(f'SELECT * FROM "{name}"')] if available else []
        as_of = (clock or (lambda: datetime.now(timezone.utc)))()
        return {'tables': tables, 'capabilities': capabilities, 'as_of': as_of}
    except (sqlite3.Error, OSError) as exc:
        raise ReportLoadError('Local reporting database is missing, unreadable or incompatible.') from exc
    finally:
        if conn is not None:
            conn.close()
