import json
from datetime import timedelta

from test_reporting_application_reports import NOW, population
from cv_optimizer.reporting.assessment_reports import assessment_reports, score_band


def assessment(id, app_id, at, score=80, role='frontend', requirements=None, **extra):
    return dict(id=id, application_id=app_id, created_at=at, score=score,
                assessment_json=json.dumps(dict(role_family=role, requirements=requirements or [])),
                scoring_version='v1', prompt_version='p1', model_name='model', candidate_hash='cv', jd_hash='jd', **extra)


def test_selection_timing_and_partitions():
    facts = population([(40, None, [('applied', 0), ('interview 1', 10)]) for _ in range(5)])
    applied = NOW-timedelta(days=40)
    rows = [assessment(1, 1, (applied+timedelta(days=2)).isoformat(), role='backend'),
            assessment(2, 1, (applied+timedelta(days=11)).isoformat(), role='frontend'),
            assessment(3, 2, (applied+timedelta(days=10)).isoformat()),
            assessment(4, 3, (applied+timedelta(days=11)).isoformat()),
            assessment(5, 4, (applied+timedelta(days=1)).isoformat())]
    rows[-1]['model_name'] = 'other'
    reports = assessment_reports(facts, rows)
    targeting = reports['targeting']
    assert targeting['selections']['1']['descriptive']['id'] == 2
    assert targeting['selections']['1']['comparison']['id'] == 1
    assert targeting['selections']['2']['timing'] == 'timing-unknown'
    assert targeting['selections']['3']['timing'] == 'retrospective'
    assert targeting['selections']['5']['timing'] == 'unassessed'
    assert len({g['partition'] for g in targeting['groups'] if g.get('partition')}) == 2
    assert next(g for g in targeting['groups'] if g['dimension'] == 'role' and g['ids'] == [1])['label'] == 'backend'


def test_bands_and_distinct_skill_evidence():
    assert [score_band(n) for n in [0, 39, 40, 59, 60, 79, 80, 100, None, -1]] == [
        '0–39', '0–39', '40–59', '40–59', '60–79', '60–79', '80–100', '80–100', 'unknown', 'unknown']
    facts = population([(40, None, [('applied', 0)])])
    reqs = [dict(requirement=' React 18 ', category='technical', priority='must', is_core=True,
                 evidence_level=level, evidence_paths=['/skills/0']) for level in ['partial', 'partial', 'none', 'unknown']]
    reports = assessment_reports(facts, [assessment(1, 1, '2026-10-01', requirements=reqs)])
    category = reports['skills']['groups'][0]
    assert category['ids'] == [1] and category['gap_ids'] == [1]
    assert category['evidence']['partial'] == [1] and category['evidence']['unknown'] == [1]
    assert category['must_ids'] == category['core_ids'] == [1]
    assert reports['skills']['requirements'][0]['label'] == 'react 18'


def test_invalid_json_and_missing_fields_are_coverage():
    facts = population([(40, None, [('applied', 0)]) for _ in range(2)])
    rows = [assessment(1, 1, '2026-10-01'), assessment(2, 2, 'not-a-date')]
    rows[0]['assessment_json'] = '{'
    report = assessment_reports(facts, rows)
    assert report['skills']['coverage']['invalid_json_ids'] == [1]
    assert report['targeting']['selections']['2']['timing'] == 'timing-unknown'
