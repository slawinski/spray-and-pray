from test_reporting_application_reports import NOW
from datetime import timedelta
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


def test_latest_completed_collection_includes_errors_but_not_failed_or_future_runs():
    runs = [dict(id=i, status=status, completed_at=(NOW - timedelta(days=age)).isoformat(),
                 errors_json='["source unavailable"]' if status == 'completed_with_errors' else '[]')
            for i, status, age in [(1, 'completed', 10), (2, 'completed_with_errors', 2),
                                   (3, 'failed', 1), (4, 'running', 0), (5, 'completed_with_errors', -1)]]
    report = inventory_report({'job_postings': [], 'discovery_runs': runs}, NOW)
    assert report['last_completed_at'] == NOW - timedelta(days=2)
    assert report['freshness_days'] == 2
    assert report['runs'][1]['status'] == 'completed_with_errors'
    assert report['runs'][1]['errors'] == ['source unavailable']
    assert report['runs'][1]['errors_state'] == 'recorded'
