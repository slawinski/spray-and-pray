"""Assemble one allowlisted evidence bundle after closing its read transaction."""

import logging
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlsplit
from uuid import uuid4

from .reader import read_snapshot
from .facts import build_facts, select_scope
from .application_reports import application_reports, group
from .assessment_reports import assessment_reports
from .inventory_report import inventory_report
from .sankey_report import sankey_report
from .insights import build_brief

logger = logging.getLogger(__name__)


def safe_url(value):
    try:
        url = urlsplit(value or '')
        return value if url.scheme.lower() in ('http', 'https') and url.netloc else None
    except ValueError:
        return None


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def build_snapshot(*, start='', end='', profile='', source='', path=None, clock=None):
    extracted = read_snapshot(path, clock=clock)
    tables, capabilities, as_of = (extracted[k] for k in ('tables', 'capabilities', 'as_of'))
    facts = build_facts(tables, as_of)
    selection = select_scope(facts, start=start, end=end, profile=profile, source=source)
    selected = selection['facts']
    reports = application_reports(selected)
    if capabilities['match_assessments']:
        try:
            reports.update(assessment_reports(selected, tables['match_assessments'], as_of))
        except (ValueError, TypeError, KeyError):
            logger.exception('Historical assessment report failed')
            reports.update({k: {'state': 'failed', 'title': k.title(), 'groups': [], 'reason': 'Historical assessment report failed. Refresh to retry.'} for k in ('targeting', 'skills')})
    else:
        reports.update({k: {'state': 'unavailable', 'title': k.title(), 'groups': [], 'reason': 'Assessment table unavailable.'} for k in ('targeting', 'skills')})
    inventory_tables = {k: tables[k] for k in ('job_postings', 'job_source_refs', 'discovery_runs') if capabilities[k]}
    try:
        reports['inventory'] = inventory_report(inventory_tables, as_of)
    except (ValueError, TypeError, KeyError):
        logger.exception('Inventory report failed')
        reports['inventory'] = {'title': 'Opportunity inventory', 'state': 'failed', 'groups': [], 'reason': 'Inventory report failed. Refresh to retry.'}
    reports['sankey'] = sankey_report(selected)
    skills = reports['skills']
    skills['gap_groups'] = [group(['gap', g['key']], g['label'] + ' · must-have/core partial or none', g['gap_ids'], g['gap_ids'],
                                 analytical_subset='Distinct must-have/core partial-or-none union') | {'key': g['key'] + ':gap'} for g in skills['groups']]
    brief = build_brief(reports)
    applications = {}
    included_ids = set(selection['ids'] + selection['never_applied_ids'] + selection['unknown_date_excluded_ids'])
    for f in facts:
        if f['id'] not in included_ids:
            continue
        record = {k: f.get(k) for k in ('id', 'company', 'role', 'source', 'raw_source', 'profile', 'applied_at', 'interview_at',
                                       'current_status', 'age_days', 'stage_age_days', 'diagnostics', 'raw_history')}
        record['job_url'] = safe_url(f.get('job_url'))
        record['assessment'] = reports['targeting'].get('selections', {}).get(str(f['id']))
        applications[str(f['id'])] = record
    postings = {}
    refs_by_posting = defaultdict(list)
    for ref in inventory_tables.get('job_source_refs', []):
        refs_by_posting[ref['job_posting_id']].append(ref)
    for p in inventory_tables.get('job_postings', []):
        record = {k: p.get(k) for k in ('id', 'company', 'role', 'description', 'location_text', 'work_model', 'seniority',
                                       'employment_type', 'salary_min', 'salary_max', 'salary_currency', 'salary_period', 'salary_raw',
                                       'first_seen_at', 'last_seen_at')}
        record['canonical_url'] = safe_url(p.get('canonical_url'))
        record['source_refs'] = [{k: r.get(k) for k in ('id', 'source', 'external_id', 'first_seen_at', 'last_seen_at')}
                                 | {'source_url': safe_url(r.get('source_url')), 'apply_url': safe_url(r.get('apply_url'))}
                                 for r in refs_by_posting[p['id']]]
        postings[str(p['id'])] = record
    return serialize({'snapshot_id': str(uuid4()), 'retrieved_at': as_of, 'as_of': as_of,
                      'scope': selection['scope'], 'filter_options': selection['options'], 'selected_ids': selection['ids'],
                      'never_applied_ids': selection['never_applied_ids'], 'unknown_date_excluded_ids': selection['unknown_date_excluded_ids'],
                      'capabilities': capabilities, 'reports': reports, 'brief': brief,
                      'applications': applications, 'postings': postings})
