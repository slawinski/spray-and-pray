"""Independent captured-posting inventory; never inherit application scope."""

import json
from collections import defaultdict

from .application_reports import group
from .facts import timestamp, days
from .normalization import normalize


def inventory_report(tables, as_of):
    if 'job_postings' not in tables:
        return {'title': 'Opportunity inventory', 'state': 'unavailable', 'reason': 'Discovery tables unavailable', 'groups': []}
    postings = sorted(tables['job_postings'], key=lambda p: p['id'])
    groups, salaries = [], defaultdict(list)
    for dimension in ('work_model', 'seniority'):
        buckets = defaultdict(list)
        for p in postings:
            buckets[normalize(p.get(dimension))].append(p)
        groups.extend(group([dimension, key], key, rows, dimension=dimension,
                            raw_variants=sorted({str(p.get(dimension)) for p in rows})) for key, rows in sorted(buckets.items()))
    for p in postings:
        key = tuple(normalize(p.get(k)) for k in ('salary_currency', 'salary_period', 'employment_type'))
        salaries[key].append(p)
    salary_groups = [group(['salary', *key], ' / '.join(key), rows,
                           comparable='unknown' not in key, ranges=[{'id': p['id'], 'min': p.get('salary_min'), 'max': p.get('salary_max')} for p in rows])
                     for key, rows in sorted(salaries.items())]
    runs = []
    for run in sorted(tables.get('discovery_runs', []), key=lambda r: r['id']):
        try:
            errors = json.loads(run.get('errors_json') or '[]')
            state = 'recorded' if isinstance(errors, (list, dict)) else 'malformed'
        except (TypeError, ValueError):
            errors, state = run.get('errors_json'), 'malformed'
        runs.append({k: run.get(k) for k in ('id', 'status', 'started_at', 'completed_at')} | {'errors': errors, 'errors_state': state})
    completed = [timestamp(r.get('completed_at')) for r in runs if r['status'] == 'completed']
    completed = [at for at in completed if at and at <= as_of]
    last = max(completed) if completed else None
    stale, unknown_freshness = [], []
    for p in postings:
        age = days(as_of, timestamp(p.get('last_seen_at')))
        if age is None:
            unknown_freshness.append(p['id'])
        elif age > 30:
            stale.append(p['id'])
    return {'title': 'Opportunity inventory', 'state': 'ready' if postings else 'empty',
            'scope': 'All captured postings · independent of application filters',
            'population_ids': [p['id'] for p in postings], 'groups': groups, 'salary_groups': salary_groups,
            'runs': runs, 'runs_available': 'discovery_runs' in tables,
            'last_completed_at': last, 'freshness_days': days(as_of, last),
            'older_than_30_days_ids': stale, 'unknown_freshness_ids': unknown_freshness,
            'conversion_yield': None, 'coverage': {dimension: sum(normalize(p.get(dimension)) != 'unknown' for p in postings)
                                                   for dimension in ('work_model', 'seniority')},
            'caveat': 'Captured inventory, not the current market. Older than 30 days does not mean inactive. Incompatible salary units/employment types are separate; no currency conversion, annualization or open-range averaging. Source-to-application yield is unavailable without reliable linkage.'}
