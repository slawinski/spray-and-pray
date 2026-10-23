from test_reporting_application_reports import NOW
from cv_optimizer.reporting.inventory_report import inventory_report


def test_inventory_units_missing_freshness_and_errors():
    postings = [dict(id=1, salary_currency='USD', salary_period='hour', employment_type='contract',
                     salary_min=50, salary_max=None, last_seen_at='2026-01-01'),
                dict(id=2, salary_currency='PLN', salary_period='month', employment_type='employment',
                     salary_min=10000, salary_max=20000),
                dict(id=3, salary_min=1)]
    report = inventory_report({'job_postings': postings, 'discovery_runs': [
        dict(id=1, status='failed', completed_at='2026-10-01', errors_json='not-json')],
        'job_source_refs': []}, NOW)
    assert report['population_ids'] == [1, 2, 3]
    assert len(report['salary_groups']) == 3
    assert next(g for g in report['salary_groups'] if not g['comparable'])['ids'] == [3]
    assert report['older_than_30_days_ids'] == [1]
    assert report['runs'][0]['errors_state'] == 'malformed'
    assert report['groups'][0]['label'] == 'unknown'
    assert report['conversion_yield'] is None


def test_missing_inventory_is_unavailable():
    assert inventory_report({}, NOW)['state'] == 'unavailable'
