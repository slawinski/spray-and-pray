"""Acceptance journeys use synthetic databases only, through the actual HTTP stack."""

import json
import sqlite3
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import server
from cv_optimizer.reporting import service
from test_reporting_application_reports import NOW
from test_reporting_browser_state import run_node


@pytest.fixture
def recorded_search(temp_db, monkeypatch):
    with sqlite3.connect(temp_db.DB_PATH) as conn:
        conn.execute('DROP TRIGGER trg_status_forward_only')  # Synthetic historical undo / revisit cases.
        paths = [[('draft', 0)], [('applied', 0), ('ghosted', 0)],
                 [('applied', 0), ('ghosted', 0), ('interview 1', 4), ('rejected', 5)],
                 [('applied', 0), ('rejected', 2)], [('applied', 0), ('interview 3', 7)],
                 [('applied', 0), ('interview 1', 1), ('ghosted', 2)],
                 [('applied', 0), ('draft', 1)], [('applied', 0), ('withdrawn', 3)],
                 [('applied', 0), ('offer', 8), ('accepted', 10)], [('applied', 0)]]
        for i, path in enumerate(paths, 1):
            conn.execute('INSERT INTO applications(id,company,role,source,cv_profile) VALUES (?,?,?,?,?)',
                         (i, '<script>Example</script>', 'Engineer', 'Recruiter Outreach' if i % 2 else None, 'it' if i % 2 else 'mechanical_engineering'))
            age = 5 if i == 2 else 40
            for status, offset in path:
                conn.execute('INSERT INTO status_history(application_id,status,transitioned_at) VALUES (?,?,?)',
                             (i, status, (NOW-timedelta(days=age-offset)).isoformat()))
        for i, at in [(3, '2026-09-14'), (4, '2026-09-20'), (5, '2026-09-13')]:
            data = {'role_family': 'Front-End', 'requirements': [dict(requirement='React 18', category='technical', priority='must', is_core=True, evidence_level=level, evidence_paths=['/skills/0']) for level in ('partial','none','unknown')]}
            conn.execute('INSERT INTO match_assessments(application_id,score,label,confidence,base_score,assessment_json,candidate_hash,jd_hash,scoring_version,prompt_version,model_name,created_at) VALUES (?,80,\'fit\',\'high\',80,?,\'cv\',\'jd\',\'v1\',\'p1\',\'model\',?)', (i,json.dumps(data),at))
        for currency, period, employment in [('USD','hour','contract'),('PLN','month','employment'),(None,None,None)]:
            conn.execute("INSERT INTO job_postings(company,role,description,description_hash,salary_min,salary_max,salary_currency,salary_period,employment_type,last_seen_at) VALUES ('Inventory','Engineer','<b>plain text</b>','hash',10,20,?,?,?,'2026-01-01')", (currency,period,employment))
        conn.execute("INSERT INTO discovery_runs(status,completed_at,errors_json) VALUES ('failed','2026-01-01','[\"Synthetic source error\"]')")
    original = service.read_snapshot
    monkeypatch.setattr(service, 'read_snapshot', lambda path=None, clock=None: original(path, clock=lambda: NOW))
    for helper in ('init_db', '_connect', 'insert_application', 'insert_status'):
        monkeypatch.setattr(temp_db, helper, lambda *a, **k: pytest.fail('Reporting used a writer'))
    return temp_db.DB_PATH


def logical_dump(path):
    with sqlite3.connect(path) as conn:
        return list(conn.iterdump())


def test_acceptance_examples_reconcile_all_scopes_and_refresh(recorded_search, monkeypatch):
    before = logical_dump(recorded_search)
    client = TestClient(server.app)
    assert client.get('/reports').status_code == 200
    first = client.get('/api/reports/snapshot').json()
    assert first['never_applied_ids'] == [1]
    assert first['selected_ids'] == list(range(2,11))
    assert first['brief']['state'] == 'insufficient'
    assert first['applications']['2']['current_status'] == 'ghosted'
    assert first['applications']['2']['age_days'] == 5
    assert any(g['ids'] == [2] and g['rate'] is None for g in first['reports']['cohorts']['groups'])
    assert 'unknown' in [g['label'] for g in first['reports']['channel']['groups']]
    assert first['reports']['targeting']['selections']['4']['timing'] == 'retrospective'
    assert first['reports']['targeting']['selections']['2']['timing'] == 'unassessed'
    assert first['reports']['skills']['groups'][0]['gap_ids'] == [3,4,5]
    assert len(first['reports']['inventory']['salary_groups']) == 3
    assert first['reports']['inventory']['older_than_30_days_ids'] == [1,2,3]
    for query in ('?profile=it', '?source=recruiter', '?start=2026-10-01&end=2026-10-23', '?start=2000-01-01&end=2000-01-02'):
        bundle = client.get('/api/reports/snapshot'+query).json()
        selected = set(bundle['selected_ids'])
        assert bundle['reports']['inventory']['population_ids'] == [1,2,3]
        for name, report in bundle['reports'].items():
            if name == 'inventory':
                continue
            for key in ('groups','comparisons','descriptive','requirements','gap_groups','current','rejections'):
                for g in report.get(key, []):
                    assert set(g['ids']) <= selected
                    assert g['denominator'] == len(g['ids']) == len(set(g['ids']))
                    assert set(g['numerator_ids']) <= set(g['ids'])
        for lead in bundle['brief']['leads']:
            report = bundle['reports'][lead['report']]
            group = next(g for key in ('groups','comparisons','gap_groups') for g in report.get(key,[]) if g['key'] == lead['group_key'])
            assert group['ids'] == lead['ids']
    assert client.get('/api/reports/snapshot?start=bad').status_code == 422
    from cv_optimizer import db
    with monkeypatch.context() as failed_load:
        failed_load.setattr(db, 'DB_PATH', recorded_search.parent / 'missing.db')
        assert client.get('/api/reports/snapshot').status_code == 503
        assert client.get('/reports').status_code == 200
        assert not db.DB_PATH.exists()
    refreshed = client.get('/api/reports/snapshot').json()
    assert refreshed['snapshot_id'] != first['snapshot_id']
    assert logical_dump(recorded_search) == before
    with sqlite3.connect(recorded_search) as conn:
        conn.execute("INSERT INTO status_history(application_id,status,transitioned_at) VALUES (2,'interview 1','2026-10-22')")
    after_writer = logical_dump(recorded_search)
    next_bundle = client.get('/api/reports/snapshot').json()
    assert next_bundle['applications']['2']['current_status'] == 'interview 1'
    assert first['applications']['2']['current_status'] == 'ghosted'
    assert logical_dump(recorded_search) == after_writer


def test_fixture_bundle_all_presentations_and_dom_navigation(recorded_search):
    before = logical_dump(recorded_search)
    bundle = TestClient(server.app).get('/api/reports/snapshot').json()
    # Execute the actual frontend, including hash routing and focus, without network or npm dependencies.
    run_node(r"""
    const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
    const bundle=JSON.parse(BUNDLE);
    const elements={}, events={}, requests=[];
    function element(id) {return elements[id] ||= {innerHTML:'',textContent:'',hidden:false,value:'',addEventListener(type,fn){this[type]=fn},append(){},focus(){this.focused=true}};}
    for(const id of ['filters','refresh','content','scope','load-state','navigation','evidence','evidence-heading']) element(id);
    const fields=Object.fromEntries(['start','end','profile','source'].map(k=>[k,element(k)]));
    elements.filters.elements={namedItem:k=>fields[k]};
    const context={URL,URLSearchParams,console,document:{getElementById:element,createTextNode:t=>t},location:new URL('http://local/reports'),
      history:{replaceState(_,__,url){context.location=new URL(url)},pushState(_,__,url){context.location=new URL(url)}},
      addEventListener:(type,fn)=>events[type]=fn,
      fetch:async(url,opts)=>{requests.push(url);return {ok:true,json:async()=>bundle}}};
    vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
    (async()=>{
      await new Promise(resolve=>setImmediate(resolve));
      assert.match(elements.content.innerHTML,/Where to focus next/);
      for(const report of ['channel','cohorts','stages','targeting','skills','aging','inventory','sankey']) {
        context.location.hash=report; events.hashchange();
        assert.match(elements.content.innerHTML,/<caption>/);
        assert.ok(!elements.content.innerHTML.includes('<script>Example</script>'));
      }
      const group=bundle.reports.channel.groups[0];
      context.location.hash='channel/'+encodeURIComponent(group.key)+'/all'; events.hashchange();
      assert.equal(elements.evidence.hidden,false);
      assert.equal(elements['evidence-heading'].focused,true);
      assert.match(elements.evidence.innerHTML,/&lt;script&gt;Example/);
      assert.equal(requests.length,1,'navigation must not query again');
      context.location.hash='channel/obsolete/all'; events.hashchange();
      assert.equal(context.location.hash,'#channel');
      assert.equal(elements.evidence.hidden,true);
    })().catch(e=>{console.error(e);process.exitCode=1});
    """.replace('BUNDLE', json.dumps(json.dumps(bundle))))
    assert logical_dump(recorded_search) == before
