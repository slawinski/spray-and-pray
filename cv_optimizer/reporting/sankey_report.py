"""Position-aware paths with shared, right-aligned outcome endpoints."""

from collections import defaultdict

from cv_optimizer.sankey import clean_chain
from .application_reports import group, model, TIME_CAVEAT
from .facts import interview


MID_INTERVIEW_WAITING = 'No recorded outcome · mid-interview'


def status_label(status, engaged=False):
    if status == 'ghosted':
        return 'No recorded outcome · ' + ('after engagement' if engaged else 'pre-interview')
    return status


def sankey_report(facts):
    pairs, links, current, nodes = (defaultdict(list) for _ in range(4))
    chains = []
    for f in facts:
        chain = clean_chain([e['status'] for e in f['history']])
        if interview(f['current_status']) and f['stage_age_days'] is not None and f['stage_age_days'] >= 30:
            chain.append(MID_INTERVIEW_WAITING)
        chains.append(chain)
    final_position = max((len(chain)-1 for chain in chains), default=0)
    final_statuses = {'rejected', 'withdrawn', 'ghosted', MID_INTERVIEW_WAITING}
    for f, chain in zip(facts, chains):
        current[status_label(f['current_status'], f['engaged'])].append(f)
        labels = [status_label(s, f['engaged']) for s in chain]
        path = [(final_position, label) if chain[position] in final_statuses and position == len(chain)-1
                else (position, label+' (later reopened)' if chain[position] in final_statuses else label)
                for position, label in enumerate(labels)]
        for node in path:
            nodes[node].append(f['id'])
        for position in range(len(chain)-1):
            pairs[chain[position], chain[position+1], labels[position], labels[position+1]].append(f['id'])
            links[path[position], path[position+1]].append(f['id'])
    return model('Recorded application paths',
                  [group(['transition', a, b, la, lb], f'{la} → {lb}', ids, occurrences=len(ids),
                         derived=b == MID_INTERVIEW_WAITING, **{'from': a, 'to': b})
                  for (a, b, la, lb), ids in sorted(pairs.items())], facts,
                  TIME_CAVEAT + ' Link weights count path-step occurrences, not current statuses or distinct applications. '
                  'Mid-interview waiting is inferred after 30 days without a change in interview step; it does not change recorded statuses or history. '
                  'Draft preparation and transient ghosted steps are omitted.',
                 nodes=[{'key': f'{position}:{label}', 'position': position, 'label': label,
                          'ids': sorted(set(ids)), 'count': len(ids), 'derived': label == MID_INTERVIEW_WAITING}
                         for (position, label), ids in sorted(nodes.items())],
                  links=[{'source': f'{p}:{a}', 'target': f'{q}:{b}', 'source_position': p, 'target_position': q,
                           'count': len(ids), 'ids': sorted(set(ids)), 'derived': b == MID_INTERVIEW_WAITING}
                          for ((p, a), (q, b)), ids in sorted(links.items())],
                 current=[group(['current', label], label, members) for label, members in sorted(current.items())])
