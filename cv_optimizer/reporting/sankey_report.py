"""Position-aware paths cannot become cyclic even when history revisits a status."""

from collections import defaultdict

from cv_optimizer.sankey import clean_chain
from .application_reports import group, model, TIME_CAVEAT


def status_label(status, engaged=False):
    if status == 'ghosted':
        return 'No recorded outcome · ' + ('after engagement' if engaged else 'pre-interview')
    return status


def sankey_report(facts):
    pairs, links, current, nodes = (defaultdict(list) for _ in range(4))
    for f in facts:
        chain = clean_chain([e['status'] for e in f['history']])
        current[status_label(f['current_status'], f['engaged'])].append(f)
        labels = [status_label(s, f['engaged']) for s in chain]
        for position, label in enumerate(labels):
            nodes[position, label].append(f['id'])
        for position in range(len(chain)-1):
            pairs[chain[position], chain[position+1], labels[position], labels[position+1]].append(f['id'])
            links[position, labels[position], labels[position+1]].append(f['id'])
    return model('Recorded application paths',
                 [group(['transition', a, b, la, lb], f'{la} → {lb}', ids, occurrences=len(ids), **{'from': a, 'to': b})
                  for (a, b, la, lb), ids in sorted(pairs.items())], facts,
                 TIME_CAVEAT + ' Link weights count transition occurrences, not current statuses or distinct applications. Draft preparation and transient ghosted steps are omitted.',
                 nodes=[{'key': f'{position}:{label}', 'position': position, 'label': label,
                         'ids': sorted(set(ids)), 'count': len(ids)} for (position, label), ids in sorted(nodes.items())],
                 links=[{'source': f'{p}:{a}', 'target': f'{p+1}:{b}', 'source_position': p, 'target_position': p+1,
                         'count': len(ids), 'ids': sorted(set(ids))} for (p, a, b), ids in sorted(links.items())],
                 current=[group(['current', label], label, members) for label, members in sorted(current.items())])
