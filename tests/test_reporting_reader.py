import sqlite3
from datetime import datetime, timezone

import pytest

from cv_optimizer.reporting.reader import ReportLoadError, read_snapshot

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def test_missing_does_not_initialize(tmp_path):
    path = tmp_path / 'absent.db'
    with pytest.raises(ReportLoadError):
        read_snapshot(path, clock=lambda: NOW)
    assert not path.exists()


def test_read_only_and_optional_tables(temp_db, monkeypatch):
    path = temp_db.DB_PATH
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO applications(company, role) VALUES ('Example', 'Engineer')")
        conn.execute("INSERT INTO status_history(application_id,status) VALUES (1,'applied')")
        conn.execute('DROP TABLE match_assessments')
        before = list(conn.iterdump())
    monkeypatch.setattr(temp_db, 'init_db', lambda: pytest.fail('writer called'))
    monkeypatch.setattr(temp_db, '_connect', lambda: pytest.fail('writer connection'))
    snapshot = read_snapshot(clock=lambda: NOW)
    assert snapshot['tables']['applications'][0]['company'] == 'Example'
    assert not snapshot['capabilities']['match_assessments']
    with sqlite3.connect(path) as conn:
        assert list(conn.iterdump()) == before


def test_wal_consistent_between_selects(temp_db, monkeypatch):
    original = sqlite3.connect
    writer = original(temp_db.DB_PATH)
    writer.execute("INSERT INTO applications(company,role) VALUES ('Before','Engineer')")
    writer.commit()

    class Interleaved(sqlite3.Connection):
        def execute(self, sql, *args):
            result = super().execute(sql, *args)
            if sql == 'SELECT * FROM "applications"':
                writer.execute("INSERT INTO applications(company,role) VALUES ('After','Engineer')")
                writer.execute("INSERT INTO status_history(application_id,status) VALUES (2,'applied')")
                writer.commit()
            return result

    monkeypatch.setattr(sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=Interleaved))
    first = read_snapshot(clock=lambda: NOW)
    assert len(first['tables']['applications']) == 1
    assert first['tables']['status_history'] == []
    monkeypatch.setattr(sqlite3, 'connect', original)
    second = read_snapshot(clock=lambda: NOW)
    assert len(second['tables']['applications']) == 2
    assert len(second['tables']['status_history']) == 1
    writer.close()
