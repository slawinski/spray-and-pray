"""Deterministic investigation leads with exact snapshot-local supporting groups."""

from itertools import combinations


def build_brief(reports):
    candidates, reasons = [], []

    def lead(kind, report, g, text, caveat, count=None):
        candidates.append({'kind': kind, 'report': report, 'group_key': g['key'],
                           'text': text, 'caveat': caveat, 'ids': g['ids'],
                           'numerator_ids': g.get('numerator_ids', []), 'denominator': g['denominator'],
                           'numerator': g.get('numerator', 0), 'support_count': count if count is not None else g['denominator']})

    for name in ('channel', 'targeting'):
        report = reports.get(name, {})
        groups = [g for g in report.get('comparisons', []) if g['label'] != 'unknown' and g['denominator'] >= 10
                  and g['rate'] is not None and (name != 'targeting' or g.get('comparable'))]
        qualifying = False
        for a, b in combinations(sorted(groups, key=lambda g: g['key']), 2):
            if name == 'targeting' and (a['partition'], a['dimension']) != (b['partition'], b['dimension']):
                continue
            if a['numerator'] + b['numerator'] < 5 or abs(a['rate'] - b['rate']) < .1 - 1e-12:
                continue
            high, low = sorted((a, b), key=lambda g: (-g['rate'], g['key']))
            qualifying = True
            lead('qualified comparison', name, high,
                 f"Investigate {high['label']}: {high['numerator']}/{high['denominator']} attained an interview within 30 recorded days, versus {low['numerator']}/{low['denominator']} for {low['label']}.",
                 report.get('caveat', '') + ' Fully observed 30-day analytical subset, not an allocation recommendation.')
            candidates[-1]['comparison_group_key'] = low['key']
            candidates[-1]['comparison_ids'] = low['ids']
        if not qualifying:
            reasons.append(f'{name}: insufficient data for a comparable 30-day contrast (two known groups of 10+, five interviews, ≥10 percentage points; targeting also requires comparable pre-outcome provenance).')
    channel = reports.get('channel', {})
    total_interviews = sum(g['numerator'] for g in channel.get('groups', []))
    if total_interviews >= 5:
        for g in channel.get('groups', []):
            if g['label'] != 'unknown' and g['numerator'] >= 3:
                lead('descriptive concentration', 'channel', g,
                     f"Inspect {g['label']}: {g['numerator']}/{total_interviews} recorded interviews came from this source.",
                     f"Known source coverage {channel.get('known_source_count', 0)}/{len(channel.get('population_ids', []))}. Recruiter selection bias applies; this is not a source success-rate comparison.",
                     g['numerator'])
    skills = reports.get('skills', {})
    valid = len(skills.get('coverage', {}).get('valid_assessed_ids', []))
    if valid >= 10:
        for g in skills.get('groups', []):
            if g['label'] != 'unknown' and len(g['gap_ids']) >= 5:
                selection = {'key': g['key'] + ':gap', 'label': g['label'] + ' · must-have/core partial or none',
                             'ids': g['gap_ids'], 'denominator': len(g['gap_ids']), 'numerator': len(g['gap_ids']),
                             'numerator_ids': g['gap_ids'], 'analytical_subset': 'Distinct must-have/core partial-or-none union'}
                lead('recurring evidence inspection', 'skills', selection,
                     f"Audit {g['label']} CV evidence: {len(g['gap_ids'])}/{valid} valid assessed applications contain must-have/core partial or none evidence ({len(g['gap_partial_ids'])} partial; {len(g['gap_none_ids'])} none; overlap counted once).",
                     skills.get('caveat', ''), len(g['gap_ids']))
    rank = {'qualified comparison': 0, 'descriptive concentration': 1, 'recurring evidence inspection': 2}
    candidates.sort(key=lambda l: (rank[l['kind']], -l['support_count'], l['report'], l['group_key']))
    leads, seen = [], set()
    for candidate in candidates:
        identity = (candidate['report'], tuple(candidate['ids']))
        if identity not in seen:
            leads.append(candidate)
            seen.add(identity)
        if len(leads) == 3:
            break
    return {'state': 'ready' if leads else 'insufficient', 'leads': leads,
            'message': 'Patterns worth investigating, not prescribed allocations.' if leads else 'Insufficient data for a search-focus conclusion.',
            'reasons': reasons}
