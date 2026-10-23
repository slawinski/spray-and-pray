from test_reporting_application_reports import population
from cv_optimizer.reporting.application_reports import application_reports
from cv_optimizer.reporting.insights import build_brief


def reports(a=10, b=10, wins=5, age=40):
    facts = population([(age, source, [('applied', 0)] + ([('interview 1', 7)] if i < win else []))
                        for source, n, win in [('referral', a, wins), ('linkedin', b, 0)] for i in range(n)])
    return application_reports(facts)


def test_thresholds_and_exact_comparison_evidence():
    report = reports()
    brief = build_brief(report)
    lead = brief['leads'][0]
    assert lead['kind'] == 'qualified comparison'
    assert '30' in lead['text'] and 'caus' not in lead['text']
    g = next(g for g in report['channel']['comparisons'] if g['key'] == lead['group_key'])
    assert lead['ids'] == g['ids'] and lead['numerator_ids'] == g['numerator_ids']
    assert build_brief(reports(a=9))['leads'][0]['kind'] == 'descriptive concentration'
    assert build_brief(reports(wins=4))['state'] == 'insufficient'
    assert all(l['kind'] != 'qualified comparison' for l in build_brief(reports(age=29.999))['leads'])


def test_determinism_and_insufficient_reason():
    report = reports()
    first = build_brief(report)
    report['channel']['groups'].reverse()
    report['channel']['comparisons'].reverse()
    assert build_brief(report) == first
    assert 'insufficient data' in build_brief(application_reports([]))['message'].lower()


def test_ten_percentage_point_boundary():
    report = reports(a=50, b=50)
    assert build_brief(report)['leads'][0]['kind'] == 'qualified comparison'
    report = reports(a=51, b=50)
    assert all(l['kind'] != 'qualified comparison' for l in build_brief(report)['leads'])
