from test_reporting_application_reports import population
from cv_optimizer.reporting.sankey_report import sankey_report
from cv_optimizer.sankey import clean_chain, build_sankey_flows


def test_shared_cleaner_waiting_and_single_stage():
    assert clean_chain(['draft', 'applied', 'ghosted', 'interview 1']) == ['applied', 'interview 1']
    facts = population([(40, None, [('draft', 0)]),
                        (40, None, [('applied', 0), ('ghosted', 0), ('interview 1', 1)]),
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
