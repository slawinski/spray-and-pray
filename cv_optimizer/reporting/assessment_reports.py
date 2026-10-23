"""Historical assessment parsing without importing scoring or generation machinery."""

import json
import math
from collections import defaultdict

from .application_reports import group, model, age_summary, thirty_day_groups
from .facts import timestamp, interview
from .normalization import normalize, role_key

CATEGORIES = {'role_scope', 'technical', 'experience_delivery', 'engineering_practices',
              'domain_product', 'collaboration_communication', 'education_certifications',
              'language', 'location_work_model'}
LEVELS = ('direct', 'framework_transfer', 'strong_transfer', 'framework_depth_gap', 'partial', 'none', 'unknown')
PROVENANCE = ('scoring_version', 'prompt_version', 'model_name', 'candidate_hash')


def score_band(score):
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
        return 'unknown'
    return '0–39' if score < 40 else '40–59' if score < 60 else '60–79' if score < 80 else '80–100'


def parse_assessment(row):
    try:
        data = json.loads(row.get('assessment_json') or '')
        valid = isinstance(data, dict)
    except (ValueError, TypeError):
        data, valid = {}, False
    if not valid:
        data = {}
    return {**{k: row.get(k) for k in ('id', 'application_id', 'score', 'created_at', 'jd_hash', *PROVENANCE)},
            'at': timestamp(row.get('created_at')), 'data': data, 'valid_json': valid,
            'band': score_band(row.get('score')), 'role': role_key(data.get('role_family')),
            'partition': json.dumps([row.get(k) for k in PROVENANCE], separators=(',', ':')),
            'comparable': all(row.get(k) for k in PROVENANCE)}


def select_assessments(facts, rows, as_of):
    by_app = defaultdict(list)
    for row in rows:
        by_app[row['application_id']].append(parse_assessment(row))
    selections = {}
    for f in facts:
        raw = by_app[f['id']]
        valid = sorted([a for a in raw if a['at'] and a['at'] <= as_of], key=lambda a: (a['at'], a['id']))
        latest = valid[-1] if valid else None
        outcome = next((e['at'] for e in f['history'] if f['applied_at'] and e['at'] >= f['applied_at']
                        and (interview(e['status']) or e['status'] in ('rejected', 'withdrawn', 'offer', 'accepted'))), None)
        eligible = [a for a in valid if (not outcome or a['at'] < outcome)
                    and a['band'] != 'unknown' and a['valid_json']]
        comparison = eligible[-1] if eligible and not f['interval_anomaly'] else None
        if f['interval_anomaly'] or raw and not valid or latest and outcome and latest['at'] == outcome and not comparison:
            timing = 'timing-unknown'
        elif comparison:
            timing = 'pre-outcome' if outcome else 'unresolved'
        elif latest and outcome and latest['at'] > outcome:
            timing = 'retrospective'
        else:
            timing = 'invalid' if latest else 'unassessed'
        selections[str(f['id'])] = {'descriptive': latest, 'comparison': comparison, 'timing': timing,
                                    'invalid_timestamp_count': sum(a['at'] is None for a in raw),
                                    'future_assessment_count': sum(a['at'] is not None and a['at'] > as_of for a in raw)}
    return selections


def assessment_reports(facts, rows, as_of=None):
    # Callers normally pass the reader's as_of; fixture callers can infer it from fact ages.
    if as_of is None:
        from datetime import timedelta, datetime, timezone
        as_of = next((f['applied_at'] + timedelta(days=f['age_days']) for f in facts if f['applied_at']), datetime.now(timezone.utc))
    selections = select_assessments(facts, rows, as_of)
    targeting_buckets, descriptive, categories, requirements = (defaultdict(list) for _ in range(4))
    coverage = {k: [] for k in ('assessed_ids', 'valid_assessed_ids', 'invalid_json_ids', 'missing_requirements_ids', 'malformed_requirement_ids', 'unassessed_ids')}
    for f in facts:
        selection = selections[str(f['id'])]
        latest, comparison = selection['descriptive'], selection['comparison']
        if latest:
            coverage['assessed_ids'].append(f['id'])
            for dim, label in [('score', latest['band']), ('role', latest['role'])]:
                descriptive[selection['timing'], dim, label, latest['partition']].append(f)
            if not latest['valid_json']:
                coverage['invalid_json_ids'].append(f['id'])
            else:
                coverage['valid_assessed_ids'].append(f['id'])
                reqs = latest['data'].get('requirements')
                if not isinstance(reqs, list):
                    coverage['missing_requirements_ids'].append(f['id'])
                else:
                    for req in reqs:
                        if not isinstance(req, dict) or not isinstance(req.get('requirement'), str) or not req['requirement'].strip():
                            coverage['malformed_requirement_ids'].append(f['id'])
                            continue
                        category = normalize(req.get('category'))
                        if category not in CATEGORIES:
                            category = 'unknown'
                        item = (f['id'], req)
                        categories[category].append(item)
                        requirements[normalize(req['requirement'])].append(item)
        else:
            coverage['unassessed_ids'].append(f['id'])
        if comparison:
            for dim, label in [('score', comparison['band']), ('role', comparison['role'])]:
                targeting_buckets[comparison['partition'], dim, label].append(f)
    targeting_groups, comparisons = [], []
    for (partition, dim, label), members in sorted(targeting_buckets.items()):
        assessments = [selections[str(f['id'])]['comparison'] for f in members]
        comparable = all(a['comparable'] for a in assessments)
        targeting_groups.append(group([partition, dim, label], label, members,
                                      [f['id'] for f in members if f['ever_interview']],
                                      partition=partition, dimension=dim, comparable=comparable,
                                      ages=age_summary(members), raw_variants=sorted({str(a['data'].get('role_family')) for a in assessments})))
        for g in thirty_day_groups(members, lambda f: label):
            g.update(key=json.dumps(['30-day', partition, dim, label], separators=(',', ':')),
                     partition=partition, dimension=dim, comparable=comparable)
            comparisons.append(g)

    def skill_groups(buckets, dimension):
        groups = []
        for label, entries in buckets.items():
            levels = {level: sorted({i for i, r in entries if normalize(r.get('evidence_level')) == level}) for level in LEVELS}
            levels['unknown'] = sorted({i for i, r in entries if normalize(r.get('evidence_level')) not in LEVELS or normalize(r.get('evidence_level')) == 'unknown'})
            must = sorted({i for i, r in entries if r.get('priority') == 'must'})
            core = sorted({i for i, r in entries if r.get('is_core') is True})
            gap = sorted({i for i, r in entries if (r.get('priority') == 'must' or r.get('is_core') is True)
                          and r.get('evidence_level') in ('partial', 'none')})
            groups.append(group([dimension, label], label, [i for i, _ in entries],
                                gap, dimension=dimension, evidence=levels, must_ids=must, core_ids=core,
                                must_core_ids=sorted(set(must) | set(core)), gap_ids=gap,
                                gap_partial_ids=sorted({i for i, r in entries if i in gap and r.get('evidence_level') == 'partial' and (r.get('priority') == 'must' or r.get('is_core') is True)}),
                                gap_none_ids=sorted({i for i, r in entries if i in gap and r.get('evidence_level') == 'none' and (r.get('priority') == 'must' or r.get('is_core') is True)}),
                                raw_variants=sorted({str(r.get('category') if dimension == 'category' else r['requirement']) for _, r in entries}),
                                requirement_evidence=[{'application_id': i, **r} for i, r in entries]))
        return sorted(groups, key=lambda g: (-len(g['gap_ids']), -g['denominator'], g['key']))

    descriptive_groups = [group(['descriptive', *key], f'{key[0]} · {key[2]}', members,
                                [f['id'] for f in members if f['ever_interview']],
                                timing=key[0], dimension=key[1], partition=key[3])
                          for key, members in sorted(descriptive.items())]
    for timing in ('unassessed', 'invalid', 'timing-unknown'):
        missing = [f for f in facts if selections[str(f['id'])]['timing'] == timing and not selections[str(f['id'])]['descriptive']]
        if missing:
            descriptive_groups.append(group(['coverage', timing], timing, missing, dimension='coverage', timing=timing))
    coverage = {k: sorted(set(v)) for k, v in coverage.items()}
    return {'targeting': model('Targeting fit', targeting_groups, facts,
                               'Fit measures, not interview probabilities. Pre-outcome comparisons are partitioned by scoring/prompt/model/CV provenance; retrospective and equal-time assessments do not establish precedence.',
                               descriptive=descriptive_groups, comparisons=comparisons, selections=selections, coverage=coverage),
            'skills': model('Recurring requirements and CV evidence', skill_groups(categories, 'category'), facts,
                            'Audit of latest assessed CV evidence, not necessarily pre-outcome evidence. Partial or missing CV evidence is not demonstrated inability or an employer rejection reason. Evidence columns may overlap.',
                            requirements=skill_groups(requirements, 'requirement'), coverage=coverage)}
