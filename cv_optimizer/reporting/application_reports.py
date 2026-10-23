"""History-based models. Membership, not chart arithmetic, owns every count."""

import json
from collections import defaultdict
from datetime import timedelta

from .facts import engagement_rank, interview

TIME_CAVEAT = ('Recorded time only: activation, backfilled dates and undo limit historical accuracy. '
               'No recorded outcome is unresolved, not confirmed ghosting.')
CHANNEL_CAVEAT = ('Observed associations, not causal effects. Recruiter selection bias applies; '
                  'unknown source is not a cold application. Follow-up ages differ.')


def group(key, label, members, numerator=None, *, available=True, reason=None, **extra):
    ids = sorted({f['id'] if isinstance(f, dict) else f for f in members})
    nums = sorted(set(numerator or []) & set(ids))
    return {'key': json.dumps(key, ensure_ascii=True, separators=(',', ':')),
            'label': label, 'ids': ids, 'denominator': len(ids), 'numerator_ids': nums,
            'numerator': len(nums), 'rate': len(nums)/len(ids) if ids and available else None,
            'reason': reason, **extra}


def model(title, groups, facts, caveat=TIME_CAVEAT, **extra):
    return {'title': title, 'state': 'ready' if facts else 'empty', 'groups': groups,
            'population_ids': sorted(f['id'] for f in facts), 'caveat': caveat, **extra}


def age_summary(members):
    ages = sorted(f['age_days'] for f in members if f['age_days'] is not None)
    return {'min': ages[0] if ages else None, 'max': ages[-1] if ages else None,
            'known': len(ages), 'unknown': len(members)-len(ages)}


def thirty_day_groups(facts, key_fn, label_fn=lambda k: k):
    buckets = defaultdict(list)
    for f in facts:
        if f['age_days'] is not None and f['age_days'] >= 30 and not f['interval_anomaly']:
            buckets[key_fn(f)].append(f)
    return [group(['30-day', k], label_fn(k), rows,
                  [f['id'] for f in rows if f['interview_days'] is not None and f['interview_days'] <= 30],
                  horizon=30, analytical_subset='Fully observed 30 recorded days')
            for k, rows in sorted(buckets.items())]


def application_reports(facts):
    sources, weeks, visits, rejections, waiting = (defaultdict(list) for _ in range(5))
    for f in facts:
        sources[f['source']].append(f)
        if f['applied_at']:
            monday = f['applied_at'].date() - timedelta(days=f['applied_at'].weekday())
            weeks[monday.isoformat()].append(f)
        seen = set()
        history = f['history']
        for index, event in enumerate(history):
            stage = event['status']
            rank = engagement_rank(stage)
            if rank is None or stage == 'accepted' or stage in seen:
                continue
            seen.add(stage)
            resolution = 'unresolved'
            for later in history[index+1:]:
                status = later['status']
                later_rank = engagement_rank(status)
                if status in ('rejected', 'withdrawn', 'accepted'):
                    resolution = {'rejected': 'rejection', 'withdrawn': 'withdrawal', 'accepted': 'accepted'}[status]
                    break
                if later_rank is not None and later_rank > rank:
                    resolution = 'progressed'
                    break
                if status not in ('draft', 'ghosted', stage) and later_rank is None:
                    resolution = 'unknown/anomalous'
                    break
                if status == 'draft' or later_rank is not None and later_rank < rank:
                    resolution = 'unknown/anomalous'
                    break
            visits[stage, resolution].append(f)
        for index, event in enumerate(history):
            if event['status'] == 'rejected':
                prior = [e['status'] for e in history[:index] if interview(e['status'])]
                label = max(prior, key=engagement_rank) if prior else 'No prior recorded interview'
                rejections[label].append(f)
                break
        current = f['current_status']
        if current not in ('rejected', 'withdrawn', 'accepted'):
            segment = ('Returned to preparation' if current == 'draft' else
                       'After engagement' if f['engaged'] else 'Pre-interview')
            if current not in ('draft', 'applied', 'ghosted', 'offer') and not interview(current):
                segment = 'Unknown current status'
            age = f['age_days']
            bucket = 'unknown age' if age is None else ('0–6' if age < 7 else '7–13' if age < 14 else
                                                       '14–29' if age < 30 else '30+') + ' recorded days'
            waiting[segment, bucket].append(f)
    channel = [group(['source', key], key, rows, [f['id'] for f in rows if f['ever_interview']],
                     raw_variants=sorted({str(f['raw_source']) for f in rows}), ages=age_summary(rows))
               for key, rows in sorted(sources.items())]
    cohorts = []
    for week, rows in sorted(weeks.items()):
        for horizon in (7, 14, 30):
            matured = [f['id'] for f in rows if f['age_days'] >= horizon]
            anomalies = [f['id'] for f in rows if f['interval_anomaly']]
            available = len(matured) == len(rows) and not anomalies
            cohorts.append(group([week, horizon], f'{week} · {horizon} days', rows,
                                 [f['id'] for f in rows if f['interview_days'] is not None and f['interview_days'] <= horizon],
                                 available=available, reason=None if available else 'Immature follow-up or chronology anomaly',
                                 horizon=horizon, week=week, matured_count=len(matured), matured_ids=matured,
                                 anomaly_ids=anomalies))
    stage_groups = []
    for stage in sorted({s for s, _ in visits}, key=engagement_rank):
        denominator = sorted({f['id'] for (s, _), rows in visits.items() if s == stage for f in rows})
        for resolution in ('progressed', 'rejection', 'withdrawal', 'accepted', 'unresolved', 'unknown/anomalous'):
            rows = visits.get((stage, resolution), [])
            stage_groups.append(group([stage, resolution], f'{stage} · {resolution}', rows,
                                      stage=stage, resolution=resolution, stage_visit_ids=denominator,
                                      stage_visit_count=len(denominator)))
    return {
        'channel': model('Channels', channel, facts, CHANNEL_CAVEAT + ' ' + TIME_CAVEAT,
                         known_source_count=sum(f['source'] != 'unknown' for f in facts),
                         comparisons=thirty_day_groups(facts, lambda f: f['source'])),
        'cohorts': model('Application cohorts', cohorts, facts, unknown_date_ids=[f['id'] for f in facts if not f['applied_at']]),
        'stages': model('Recorded stage progression and loss', stage_groups, facts,
                        rejections=[group(['rejection', k], k, rows) for k, rows in sorted(rejections.items())]),
        'aging': model('Unresolved waiting', [group([s, b], f'{s} · {b}', rows) for (s, b), rows in sorted(waiting.items())], facts),
    }
