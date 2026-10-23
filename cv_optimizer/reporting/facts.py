"""Canonical chronology, denominators and inclusive UTC application scope."""

import re
from datetime import datetime, timezone, date, timedelta

from .normalization import normalize, source_key


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def interview(status):
    return re.fullmatch(r'interview [1-9][0-9]*', status or '') is not None


def engagement_rank(status):
    if status == 'applied':
        return 0
    if interview(status):
        return int(status.split()[1])
    return {'offer': 1000000, 'accepted': 1000001}.get(status)


def days(later, earlier):
    return (later - earlier).total_seconds() / 86400 if earlier and later >= earlier else None


def build_facts(tables, as_of):
    histories = {}
    for event in tables.get('status_history', []):
        histories.setdefault(event['application_id'], []).append(event)
    facts = []
    for app in sorted(tables['applications'], key=lambda a: a['id']):
        raw = histories.get(app['id'], [])
        valid, diagnostics = [], []
        for event in raw:
            at = timestamp(event['transitioned_at'])
            if at is None:
                diagnostics.append('malformed_timestamp')
            elif at > as_of:
                diagnostics.append('future_timestamp')
            else:
                valid.append({**event, 'at': at})
        valid.sort(key=lambda e: (e['at'], e['id']))
        applied_at = next((e['at'] for e in valid if e['status'] == 'applied'), None)
        interviewed_at = next((e['at'] for e in valid if interview(e['status'])), None)
        anomaly = bool(applied_at and interviewed_at and interviewed_at < applied_at)
        if anomaly:
            diagnostics.append('interview_before_application')
        current = valid[-1]['status'] if valid else 'unknown'
        run = len(valid) - 1
        while run > 0 and valid[run-1]['status'] == current:
            run -= 1
        facts.append({**app, 'source': source_key(app.get('source')),
                      'raw_source': app.get('source'), 'profile': normalize(app.get('cv_profile')),
                      'history': valid, 'raw_history': raw,
                      'applied': any(e['status'] == 'applied' for e in raw),
                      'applied_at': applied_at, 'interview_at': interviewed_at,
                      'ever_interview': interviewed_at is not None,
                      'engaged': any(interview(e['status']) or e['status'] in ('offer', 'accepted') for e in valid),
                      'interview_days': None if anomaly else days(interviewed_at, applied_at) if interviewed_at else None,
                      'interval_anomaly': anomaly, 'age_days': days(as_of, applied_at),
                      'stage_age_days': days(as_of, valid[run]['at']) if valid else None,
                      'current_status': current, 'diagnostics': diagnostics})
    return facts


def select_scope(facts, *, start='', end='', profile='', source=''):
    bounds = []
    for value in (start, end):
        if value and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)):
            raise ValueError('Dates must use YYYY-MM-DD.')
        bounds.append(datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc) if value else None)
    lo, hi = bounds
    if lo and hi and lo > hi:
        raise ValueError('Start date must not follow end date.')
    options = {key: sorted({f[key] for f in facts if f['applied']}) for key in ('profile', 'source')}
    for key, value in [('profile', profile), ('source', source)]:
        if value and value not in options[key]:
            raise ValueError(f'Unsupported {key} filter.')
    population = [f for f in facts if f['applied'] and (not profile or f['profile'] == profile)
                  and (not source or f['source'] == source)]
    unknown = [f['id'] for f in population if f['applied_at'] is None and (lo or hi)]
    selected = [f for f in population if not (lo or hi) or f['applied_at'] is not None
                and (not lo or f['applied_at'] >= lo) and (not hi or f['applied_at'] < hi + timedelta(days=1))]
    return {'scope': dict(start=start, end=end, profile=profile, source=source), 'options': options,
            'facts': selected, 'ids': [f['id'] for f in selected],
            'never_applied_ids': [f['id'] for f in facts if not f['applied']],
            'unknown_date_excluded_ids': unknown}
