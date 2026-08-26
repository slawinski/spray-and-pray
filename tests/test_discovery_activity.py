"""Activity / staleness model tests (spec §41-44)."""

from datetime import datetime, timedelta, timezone

from cv_optimizer import db
from cv_optimizer.discovery.activity import (
    ABSENCES_TO_INACTIVE,
    absence_transition,
    is_aggregator_source,
    is_ats_source,
    is_stale,
    source_active_state,
)
from cv_optimizer.discovery.config import DiscoveryConfig

from conftest import make_job


def test_source_classification():
    assert is_ats_source("lever") and is_ats_source("ashby") and is_ats_source("greenhouse")
    assert is_aggregator_source("serpapi")
    assert not is_ats_source("serpapi")


def test_ats_presence_is_high_confidence_active():
    config = DiscoveryConfig()
    job = make_job(source="ashby")
    state, confidence = source_active_state(job, config)
    assert state == "active"
    assert confidence == "high"


def test_aggregator_confidence_is_medium():
    config = DiscoveryConfig()
    job = make_job(
        source="serpapi", posted_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    state, confidence = source_active_state(job, config)
    assert state == "active"
    assert confidence == "medium"


def test_aggregator_without_posted_at_is_unknown():
    config = DiscoveryConfig()
    job = make_job(source="serpapi", posted_at=None)
    state, confidence = source_active_state(job, config)
    assert state == "unknown"
    assert confidence == "medium"


def test_stale_aggregator_result_is_inactive():
    config = DiscoveryConfig(max_post_age_days=30)
    job = make_job(
        source="serpapi", posted_at=datetime.now(timezone.utc) - timedelta(days=45)
    )
    state, _ = source_active_state(job, config)
    assert state == "inactive"


def test_absence_transition_policy():
    # One absence retains the current state.
    assert absence_transition(1) is None
    # Two consecutive absences → inactive.
    assert absence_transition(ABSENCES_TO_INACTIVE) == "inactive"
    assert absence_transition(3) == "inactive"


def test_ats_absence_sweep_marks_inactive_after_two_missing_polls(temp_db):
    """A posting known from an ATS source that is not seen for two
    consecutive runs becomes inactive and can no longer be imported."""
    from cv_optimizer.discovery.service import DiscoveryService

    service = DiscoveryService(config=DiscoveryConfig())
    posting_id, _, _ = service._upsert_job(
        make_job(
            source="ashby",
            external_id="ats-1",
            company="Dash0",
            canonical_url="https://jobs.ashbyhq.com/dash0/ats-1",
        )
    )
    assert db.get_job_posting(posting_id)["active_state"] == "active"

    # Simulate a completed run that did NOT see this posting (last_seen_at
    # stays in the past): two sweeps.
    run_time = datetime.now(timezone.utc) + timedelta(minutes=1)
    service._sweep_ats_absences({"ashby"}, run_time)
    posting = db.get_job_posting(posting_id)
    assert posting["active_state"] == "active"  # first absence: retain

    run_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    service._sweep_ats_absences({"ashby"}, run_time)
    posting = db.get_job_posting(posting_id)
    assert posting["active_state"] == "inactive"


def test_ats_reappearance_resets_absences(temp_db):
    from cv_optimizer.discovery.service import DiscoveryService

    service = DiscoveryService(config=DiscoveryConfig())
    job = make_job(
        source="ashby",
        external_id="ats-2",
        company="Dash0",
        canonical_url="https://jobs.ashbyhq.com/dash0/ats-2",
    )
    posting_id, _, _ = service._upsert_job(job)

    service._sweep_ats_absences({"ashby"}, datetime.now(timezone.utc) + timedelta(minutes=1))
    assert db.get_job_posting(posting_id)["consecutive_absences"] == 1

    # Seen again → absences reset, still active.
    service._upsert_job(job.model_copy(deep=True))
    posting = db.get_job_posting(posting_id)
    assert posting["consecutive_absences"] == 0
    assert posting["active_state"] == "active"


def test_ats_absence_sweep_skips_failed_sources(temp_db):
    """Provider outages are not evidence that postings disappeared: a sweep
    with a failed source must not mark anything inactive."""
    from cv_optimizer.discovery.service import DiscoveryService

    service = DiscoveryService(config=DiscoveryConfig())
    posting_id, _, _ = service._upsert_job(
        make_job(
            source="ashby",
            external_id="ats-fail",
            company="Dash0",
            canonical_url="https://jobs.ashbyhq.com/dash0/ats-fail",
        )
    )

    run_time = datetime.now(timezone.utc) + timedelta(minutes=1)
    for _ in range(3):
        # ashby is NOT in completed_sources → sweep must skip it entirely.
        service._sweep_ats_absences(set(), run_time)
        run_time = run_time + timedelta(minutes=1)

    posting = db.get_job_posting(posting_id)
    assert posting["active_state"] == "active"
    assert posting["consecutive_absences"] == 0


def test_max_age_guard():
    config = DiscoveryConfig(max_post_age_days=30)
    fresh = datetime.now(timezone.utc) - timedelta(days=10)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    assert not is_stale(fresh, config)
    assert is_stale(old, config)
