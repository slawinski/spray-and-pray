import sqlite3

import pytest
from fastapi.testclient import TestClient

import server
from cv_optimizer.reporting import service


@pytest.fixture
def client(temp_db, monkeypatch):
    with sqlite3.connect(temp_db.DB_PATH) as conn:
        conn.execute("INSERT INTO applications(company,role,source,cv_profile,job_url) VALUES ('<script>stored</script>','Engineer','recruiter','it','javascript:alert(1)')")
        conn.execute("INSERT INTO status_history(application_id,status,transitioned_at) VALUES (1,'applied','2026-01-01')")
    monkeypatch.setattr(temp_db, 'init_db', lambda: pytest.fail('initialization'))
    monkeypatch.setattr(temp_db, '_connect', lambda: pytest.fail('write helper'))
    return TestClient(server.app)


def test_shell_snapshot_validation_and_safe_records(client):
    assert client.get('/reports').status_code == 200
    response = client.get('/api/reports/snapshot')
    assert response.status_code == 200
    bundle = response.json()
    assert set(bundle['reports']) == {'channel', 'cohorts', 'stages', 'targeting', 'skills', 'aging', 'inventory', 'sankey'}
    assert bundle['scope'] == dict(start='', end='', profile='', source='')
    assert bundle['retrieved_at'] and bundle['snapshot_id']
    assert bundle['applications']['1']['job_url'] is None
    assert 'jd_path' not in bundle['applications']['1']
    assert 'no-store' in response.headers['cache-control']
    for query in ['?start=bad', '?start=2026-10-23&end=2026-01-01', '?source=SQL%27', '?unsupported=yes']:
        assert client.get('/api/reports/snapshot'+query).status_code == 422
    assert client.get('/api/reports/snapshot?start=2020-01-01&end=2020-01-02').json()['selected_ids'] == []


def test_cors_real_stack(client):
    for path in ['/reports', '/api/reports/snapshot', '/api/reports/snapshot?start=bad']:
        for method in ('get', 'options'):
            foreign = getattr(client, method)(path, headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'GET'})
            assert foreign.status_code == 403
            assert not any(k.startswith('access-control-') for k in foreign.headers)
        same = client.get(path, headers={'Origin': 'http://testserver'})
        assert same.status_code in (200, 422)
        assert 'access-control-allow-origin' not in same.headers
    extension = client.options('/api/track', headers={'Origin': 'https://www.linkedin.com', 'Access-Control-Request-Method': 'POST'})
    assert extension.status_code == 200
    assert 'access-control-allow-origin' in extension.headers


def test_load_retry_and_optional_failure(client, temp_db, monkeypatch):
    real = temp_db.DB_PATH
    monkeypatch.setattr(temp_db, 'DB_PATH', real.parent / 'absent.db')
    assert client.get('/api/reports/snapshot').status_code == 503
    assert client.get('/reports').status_code == 200
    monkeypatch.setattr(temp_db, 'DB_PATH', real)
    monkeypatch.setattr(service, 'inventory_report', lambda *args: (_ for _ in ()).throw(ValueError('bad historical data')))
    bundle = client.get('/api/reports/snapshot').json()
    assert bundle['reports']['inventory']['state'] == 'failed'
    assert bundle['reports']['channel']['state'] == 'ready'
