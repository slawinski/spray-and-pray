"""Activity / staleness rules for discovered job postings.

Direct ATS sources (Lever, Ashby, Greenhouse) provide high-confidence
presence: a posting present in the current public feed is active; a single
missing poll does not close it (transient network/API problems), but two
consecutive absences mark it inactive.

Aggregator results (SerpApi / Google Jobs) carry lower confidence unless
independently verified by a direct ATS source.
"""

from datetime import datetime, timezone

from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.models import DiscoveredJob

ATS_SOURCES = {"lever", "ashby", "greenhouse"}
AGGREGATOR_SOURCES = {"serpapi", "google_jobs"}

ABSENCES_TO_INACTIVE = 2


def is_ats_source(source: str) -> bool:
    return source in ATS_SOURCES


def is_aggregator_source(source: str) -> bool:
    return source in AGGREGATOR_SOURCES


def age_days(posted_at: datetime | None, now: datetime | None = None) -> float | None:
    if posted_at is None:
        return None
    current = now or datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    return (current - posted_at).total_seconds() / 86400.0


def is_stale(posted_at: datetime | None, config: DiscoveryConfig) -> bool:
    """True when posted_at is older than max_post_age_days."""
    days = age_days(posted_at)
    if days is None:
        return False
    return days > config.max_post_age_days


def source_active_state(
    job: DiscoveredJob, config: DiscoveryConfig
) -> tuple[str, str]:
    """Returns (active_state, active_confidence) for a freshly seen job."""
    if is_aggregator_source(job.source):
        state = "unknown"
        confidence = "medium"
        if job.posted_at is not None:
            if is_stale(job.posted_at, config):
                state, confidence = "inactive", "medium"
            else:
                state, confidence = "active", "medium"
        elif job.active_state == "active":
            state = "active"
        return state, confidence

    if is_ats_source(job.source):
        if job.active_state == "inactive":
            return "inactive", "high"
        return "active", "high"

    # Unknown/other sources: trust the adapter's signal, medium confidence.
    return job.active_state, job.active_confidence


def absence_transition(consecutive_absences: int) -> str | None:
    """New active_state after `consecutive_absences` missed polls, if any.

    None means 'retain current state' (single absence).
    """
    if consecutive_absences >= ABSENCES_TO_INACTIVE:
        return "inactive"
    return None
