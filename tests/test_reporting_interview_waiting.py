from copy import deepcopy

from cv_optimizer.reporting.sankey_report import sankey_report
from test_reporting_application_reports import population


def test_interview_waiting_uses_thirty_days_at_current_round_without_changing_history():
    facts = population([
        (31, None, [('applied', 0), ('interview 1', 1)]),
        (31, None, [('applied', 0), ('interview 1', 1.0001)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('interview 2', 60)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('interview 1', 60)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('rejected', 2)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('withdrawn', 2)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('interview 2', 40)]),
        (70, None, [('applied', 0), ('interview 1', 1), ('offer', 2)]),
    ])
    before = deepcopy(facts)
    report = sankey_report(facts)
    waiting = next(n for n in report['nodes'] if n['label'] == 'No recorded outcome · mid-interview')
    assert waiting['ids'] == [1, 4, 7] and waiting['count'] == 3
    assert waiting['position'] == max(n['position'] for n in report['nodes'])
    incoming = [link for link in report['links'] if link['target'] == waiting['key']]
    assert sorted(i for link in incoming for i in link['ids']) == [1, 4, 7]
    assert all(link['derived'] for link in incoming)
    assert all(link['target_position'] > link['source_position'] for link in report['links'])
    assert sorted(i for g in report['groups'] if g['derived'] for i in g['ids']) == [1, 4, 7]
    assert '30 days' in report['caveat'] and 'inferred' in report['caveat']
    assert facts == before
    assert next(g for g in report['current'] if g['label'] == 'interview 1')['ids'] == [1, 2, 4]


def test_unknown_stage_age_does_not_infer_an_outcome():
    facts = population([(40, None, [('applied', 0), ('interview 1', 1)])])
    facts[0]['stage_age_days'] = None
    assert not any(n['label'] == 'No recorded outcome · mid-interview' for n in sankey_report(facts)['nodes'])


def test_new_interview_round_removes_previous_inference():
    old = population([(70, None, [('applied', 0), ('interview 1', 1)])])
    assert any(n['label'] == 'No recorded outcome · mid-interview' for n in sankey_report(old)['nodes'])
    resumed = population([(70, None, [('applied', 0), ('interview 1', 1), ('interview 2', 69)])])
    report = sankey_report(resumed)
    assert not any(n['label'] == 'No recorded outcome · mid-interview' for n in report['nodes'])
    assert not any(link['derived'] for link in report['links'])
