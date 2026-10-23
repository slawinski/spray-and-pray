from datetime import datetime, timezone, timedelta

from cv_optimizer.reporting.application_reports import application_reports
from cv_optimizer.reporting.facts import build_facts

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def population(paths):
    apps, history = [], []
    for i, (age, source, path) in enumerate(paths, 1):
        apps.append(dict(id=i, company='A', role='R', source=source))
        for status, offset in path:
            history.append(dict(id=len(history)+1, application_id=i, status=status,
                                transitioned_at=(NOW-timedelta(days=age)+timedelta(days=offset)).isoformat()))
    return build_facts(dict(applications=apps, status_history=history), NOW)


def test_channels_cohort_maturity_and_boundary():
    facts = population([(5, None, [('applied', 0), ('ghosted', 0)]),
                        (35, 'Recruiter Outreach', [('applied', 0), ('interview 1', 7)]),
                        (35, 'recruiter', [('applied', 0), ('interview 1', 7.0001)])])
    reports = application_reports(facts)
    channels = {g['label']: g for g in reports['channel']['groups']}
    assert channels['recruiter']['ids'] == [2, 3]
    assert channels['recruiter']['numerator_ids'] == [2, 3]
    assert channels['unknown']['numerator'] == 0
    cohorts = reports['cohorts']['groups']
    assert next(g for g in cohorts if g['ids'] == [1] and g['horizon'] == 7)['rate'] is None
    boundary = next(g for g in cohorts if g['ids'] == [2, 3] and g['horizon'] == 7)
    assert boundary['numerator_ids'] == [2]
    assert boundary['matured_count'] == 2


def test_stage_partitions_no_invented_visits_and_aging():
    facts = population([(40, 'referral', [('applied', 0), ('interview 3', 2), ('rejected', 3)]),
                        (2, None, [('applied', 0), ('ghosted', 0)]),
                        (20, None, [('applied', 0), ('interview 1', 1), ('ghosted', 2)]),
                        (20, None, [('applied', 0), ('draft', 1), ('draft', 2)])])
    reports = application_reports(facts)
    stages = reports['stages']['groups']
    applied = [g for g in stages if g['stage'] == 'applied']
    assert sorted(i for g in applied for i in g['ids']) == [1, 2, 3, 4]
    assert next(g for g in applied if g['resolution'] == 'progressed')['ids'] == [1, 3]
    assert reports['stages']['rejections'][0]['label'] == 'interview 3'
    aging = {g['label']: g['ids'] for g in reports['aging']['groups']}
    assert aging['Pre-interview · 0–6 recorded days'] == [2]
    assert aging['After engagement · 14–29 recorded days'] == [3]
    assert aging['Returned to preparation · 14–29 recorded days'] == [4]


def test_empty_and_partially_mature_cohort():
    assert application_reports([])['channel']['state'] == 'empty'
    facts = population([(7, None, [('applied', 0)]), (6, None, [('applied', 0)])])
    cell = next(g for g in application_reports(facts)['cohorts']['groups'] if g['horizon'] == 7)
    assert cell['rate'] is None and cell['matured_count'] == 1
