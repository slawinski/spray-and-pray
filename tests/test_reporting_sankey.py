import pytest

from test_reporting_application_reports import population
from cv_optimizer.reporting.sankey_report import sankey_report
from cv_optimizer.sankey import clean_chain, build_sankey_flows


def test_shared_cleaner_waiting_and_single_stage():
    assert clean_chain(['draft', 'applied', 'ghosted', 'interview 1']) == ['applied', 'interview 1']
    facts = population([(40, None, [('draft', 0)]),
                        (20, None, [('applied', 0), ('ghosted', 0), ('interview 1', 1)]),
                        (2, None, [('applied', 0), ('ghosted', 0)]),
                        (2, None, [('applied', 0)])])
    report = sankey_report([f for f in facts if f['applied']])
    assert report['population_ids'] == [2, 3, 4]
    assert sum(g['occurrences'] for g in report['groups']) == 2
    assert any('No recorded outcome' in g['label'] for g in report['groups'])
    assert sum(g['denominator'] for g in report['current']) == 3


def test_revisits_are_acyclic_and_occurrences_are_not_population():
    facts = population([(40, None, [('applied', 0), ('interview 1', 1), ('applied', 2), ('interview 1', 3)])])
    report = sankey_report(facts)
    assert all(link['target_position'] > link['source_position'] for link in report['links'])
    repeated = next(g for g in report['groups'] if g['from'] == 'applied')
    assert repeated['occurrences'] == 2 and repeated['ids'] == [1]
    assert build_sankey_flows([(1, e['status'], '') for e in facts[0]['history']]) == {('applied', 'interview 1'): 2, ('interview 1', 'applied'): 1}


@pytest.mark.parametrize('status', ['rejected', 'withdrawn'])
def test_final_outcomes_merge_across_interview_rounds(status):
    facts = population([(20, None, [('applied', 0), (status, 1)]),
                        (20, None, [('applied', 0), ('interview 1', 1), (status, 2)]),
                        (20, None, [('applied', 0), ('interview 1', 1), ('interview 2', 2), (status, 3)])])
    report = sankey_report(facts)
    outcomes = [n for n in report['nodes'] if n['label'] == status]
    assert len(outcomes) == 1
    assert outcomes[0]['count'] == 3 and outcomes[0]['ids'] == [1, 2, 3]
    incoming = [link for link in report['links'] if link['target'] == outcomes[0]['key']]
    assert len(incoming) == 3 and sum(link['count'] for link in incoming) == 3
    assert all(link['target_position'] > link['source_position'] for link in report['links'])


def test_final_outcomes_align_right_and_keep_waiting_segments_distinct():
    facts = population([(20, None, [('applied', 0), ('ghosted', 1)]),
                        (20, None, [('applied', 0), ('interview 1', 1), ('ghosted', 2)]),
                        (20, None, [('applied', 0), ('rejected', 1)]),
                        (20, None, [('applied', 0), ('interview 1', 1), ('interview 2', 2), ('withdrawn', 3)])])
    report = sankey_report(facts)
    outcomes = [n for n in report['nodes'] if n['label'] in ('rejected', 'withdrawn')
                or n['label'].startswith('No recorded outcome')]
    assert len(outcomes) == 4
    assert all(n['position'] == max(n['position'] for n in report['nodes']) for n in outcomes)
    assert all(link['target_position'] > link['source_position'] for link in report['links'])


@pytest.mark.parametrize('status', ['rejected', 'withdrawn'])
def test_reopened_outcome_preserves_history_without_cycling_endpoint(status):
    facts = population([(20, None, [('applied', 0), (status, 1), ('interview 1', 2), (status, 3)])])
    report = sankey_report(facts)
    assert len([n for n in report['nodes'] if n['label'] == status]) == 1
    assert any(n['label'] == status+' (later reopened)' for n in report['nodes'])
    assert all(link['target_position'] > link['source_position'] for link in report['links'])
    assert sum(g['occurrences'] for g in report['groups']) == 3
