from datetime import datetime, timezone

import pytest

from cv_optimizer.reporting.facts import build_facts, select_scope
from cv_optimizer.reporting.normalization import normalize, source_key, role_key

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


def facts(histories, **app):
    return build_facts({'applications': [{'id': 1, 'company': 'A', 'role': 'R', **app}],
                        'status_history': [dict(id=i+1, application_id=1, status=s, transitioned_at=t)
                                           for i, (s, t) in enumerate(histories)]}, NOW)


def test_ties_denominator_dates_and_current_run():
    rows = facts([('applied', '2026-10-01'), ('interview 1', '2026-10-02'),
                  ('rejected', '2026-10-02'), ('draft', '2026-10-03'), ('draft', '2026-10-04')])
    f = rows[0]
    assert f['current_status'] == 'draft'
    assert f['stage_age_days'] == 20
    assert f['ever_interview'] and f['applied']
    assert select_scope(rows, start='2026-10-01', end='2026-10-01')['ids'] == [1]
    assert select_scope(rows, start='2026-10-02')['ids'] == []
    assert f['profile'] == 'unknown'


def test_invalid_future_and_negative_intervals():
    f = facts([('interview 1', '2026-09-01'), ('applied', 'broken'),
               ('applied', '2026-10-01'), ('accepted', '2030-01-01')])[0]
    assert f['interview_days'] is None
    assert f['diagnostics'] == ['malformed_timestamp', 'future_timestamp', 'interview_before_application']
    assert f['current_status'] == 'applied'
    unknown = facts([('applied', 'broken')])
    assert select_scope(unknown)['ids'] == [1]
    assert select_scope(unknown, start='2026-01-01')['unknown_date_excluded_ids'] == [1]
    with pytest.raises(ValueError):
        select_scope(unknown, source='not-a-stored-source')


def test_normalization_is_exact():
    assert source_key(' Recruiter  Outreach ') == 'recruiter'
    assert source_key(None) == 'unknown'
    assert role_key(' Front-End ') == 'frontend'
    assert role_key('frontend lead') == 'frontend lead'
    assert normalize('  React  18 ') != normalize('React 19')
