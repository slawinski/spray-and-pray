"""Staged deduplication helpers for discovered jobs.

Level 1: exact source + external_id (enforced by UNIQUE(source, external_id)
in ``job_source_refs``).

Level 2: normalized canonical URL.

Level 3: normalized company + title + location fingerprint combined with
description similarity.

When uncertain, callers preserve two postings rather than merging distinct
vacancies.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from unidecode import unidecode

from cv_optimizer.discovery.models import DiscoveredJob

# Query parameters that never distinguish jobs and only exist for tracking.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "igshid", "gh_src",
    "ref", "ref_src", "ref_url", "src", "source",
}

# URL parameters that identify a job and must be preserved.
_KEEP_PARAMS = {"gh_jid", "jobid", "job_id", "posting", "vacancy", "req", "requisition"}

# Canonical token substitutions used in fingerprints.
_TOKEN_MAP = {
    "front-end": "frontend",
    "front end": "frontend",
    "back-end": "backend",
    "back end": "backend",
    "full-stack": "fullstack",
    "full stack": "fullstack",
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str | None) -> str | None:
    """Normalizes a job URL for dedupe purposes.

    Lowercases the hostname, removes fragments, drops tracking parameters,
    preserves job-identifying parameters, sorts remaining query pairs, and
    normalizes the trailing slash. Returns None for empty/non-http input.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None

    hostname = (parts.hostname or "").lower().removeprefix("www.")
    port = parts.port
    netloc = hostname if port is None else f"{hostname}:{port}"

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Sorted, deduped, non-tracking query parameters.
    pairs = parse_qsl(parts.query, keep_blank_values=False)
    seen: set[str] = set()
    kept = []
    for key, value in pairs:
        key_l = key.lower()
        if key_l in _TRACKING_PARAMS:
            continue
        if key_l not in _KEEP_PARAMS and value and value.isdigit() and key_l in (
            "id", "ref_id", "listing_id"
        ):
            pass  # keep id-ish params; they may distinguish jobs
        if key_l in seen:
            continue
        seen.add(key_l)
        kept.append((key, value))
    query = urlencode(sorted(kept))

    return urlunsplit((parts.scheme, netloc, path, query, ""))


def normalize_company(name: str) -> str:
    """'N-iX' → 'n ix'; 'Example Corp.' → 'example corp'."""
    text = unidecode((name or "").lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_whitespace(text)


def normalize_title(title: str) -> str:
    """'Senior Front-End Engineer' → 'senior frontend engineer'."""
    text = unidecode((title or "").lower())
    for source, target in _TOKEN_MAP.items():
        text = text.replace(source, target)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_whitespace(text)


def normalize_location(location: str | None) -> str:
    if not location:
        return ""
    text = unidecode(location.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_whitespace(text)


def fingerprint(company: str, title: str, location: str | None) -> tuple[str, str, str]:
    """Normalized (company, title, location) L3 dedupe fingerprint."""
    return (
        normalize_company(company),
        normalize_title(title),
        normalize_location(location),
    )


def description_similarity(a: str, b: str) -> float:
    na = normalize_whitespace(a)
    nb = normalize_whitespace(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


DESCRIPTION_MATCH_THRESHOLD = 0.9


def descriptions_match(a: str, b: str, threshold: float = DESCRIPTION_MATCH_THRESHOLD) -> bool:
    """True when two descriptions are confidently the same vacancy."""
    return description_similarity(a, b) >= threshold


def job_fingerprint(job: DiscoveredJob) -> tuple[str, str, str]:
    return fingerprint(job.company, job.role, job.location_text)


def canonical_url_for(job: DiscoveredJob) -> str | None:
    """Best stable URL for L2 dedupe: canonical, then apply, then source."""
    for candidate in (job.canonical_url, job.apply_url, job.source_url):
        normalized = normalize_url(candidate)
        if normalized:
            return normalized
    return None
