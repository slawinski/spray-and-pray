"""Dedupe integration at the DB level (spec §71).

Same source identity → one job_posting, one job_source_ref.
Cross-source same vacancy → one job_posting, N job_source_refs.
Same title at different locations → separate canonical postings.
"""

from datetime import datetime, timezone

from cv_optimizer import db
from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.service import DiscoveryService

from conftest import make_job

JD = (
    "We are looking for a Senior Frontend Engineer to build complex user "
    "interfaces with React and TypeScript. Strong product collaboration, "
    "accessibility, and design systems experience required. 5+ years of "
    "frontend engineering experience. Hybrid work model with an office in "
    "Warsaw, Poland."
)


def _service() -> DiscoveryService:
    config = DiscoveryConfig()
    service = DiscoveryService(config=config)
    return service


def _posting_count() -> int:
    conn = db.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    finally:
        conn.close()


def _ref_count() -> int:
    conn = db.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM job_source_refs").fetchone()[0]
    finally:
        conn.close()


def test_same_source_id_creates_one_posting_and_one_ref(temp_db):
    service = _service()
    job = make_job(
        source="lever",
        external_id="lever-abc",
        company="acmecorp",
        role="Senior Product Engineer",
        canonical_url="https://jobs.lever.co/acmecorp/abc",
    )
    first = service._upsert_job(job)
    second = service._upsert_job(job.model_copy(deep=True))

    assert first[0] == second[0]
    assert _posting_count() == 1
    assert _ref_count() == 1
    refs = db.get_job_source_refs(first[0])
    assert len(refs) == 1
    assert refs[0]["source"] == "lever"


def test_same_source_id_with_changed_jd_updates_and_resets_match(temp_db):
    service = _service()
    job = make_job(source="lever", external_id="lever-abc", company="acmecorp")
    posting_id, is_new, _ = service._upsert_job(job)
    assert is_new

    updated = job.model_copy(deep=True)
    updated.description = JD + " Additional paragraph about our observability stack."
    posting_id2, is_new2, changed = service._upsert_job(updated)

    assert posting_id == posting_id2
    assert not is_new2
    assert changed
    posting = db.get_job_posting(posting_id)
    assert "observability stack" in posting["description"]
    assert posting["match_state"] == "pending"


def test_cross_source_same_vacancy_merges_into_one_posting(temp_db):
    service = _service()
    aggregator_job = make_job(
        source="serpapi",
        external_id="google-1",
        company="Dash0",
        role="Senior Frontend Engineer",
        canonical_url="https://careers.dash0.com/jobs/123",
        apply_url="https://careers.dash0.com/jobs/123",
    )
    first = service._upsert_job(aggregator_job)

    ats_job = make_job(
        source="ashby",
        external_id="ashby-123",
        company="Dash0",
        role="Senior Frontend Engineer",
        canonical_url="https://careers.dash0.com/jobs/123",
        apply_url="https://jobs.ashbyhq.com/dash0/123",
    )
    second = service._upsert_job(ats_job)

    assert first[0] == second[0]
    assert _posting_count() == 1
    refs = db.get_job_source_refs(first[0])
    assert len(refs) == 2
    assert {r["source"] for r in refs} == {"serpapi", "ashby"}


def test_cross_source_merge_via_fingerprint_and_similar_description(temp_db):
    """Google Jobs + direct ATS posting without a shared URL still merge
    when company/title/location and descriptions match."""
    service = _service()
    first = service._upsert_job(
        make_job(
            source="serpapi",
            external_id="g-2",
            company="Dash0",
            role="Senior Frontend Engineer",
            canonical_url="https://www.google.com/search?ibp=g-2",
            description=JD,
        )
    )
    second = service._upsert_job(
        make_job(
            source="greenhouse",
            external_id="gh-424242",
            company="Dash0",
            role="Senior Frontend Engineer",
            canonical_url="https://boards.greenhouse.io/dash0/jobs/424242",
            description="About the company. " + JD + " Benefits section.",
        )
    )
    assert first[0] == second[0]
    assert _posting_count() == 1
    assert len(db.get_job_source_refs(first[0])) == 2


def test_same_title_different_location_stays_separate(temp_db):
    service = _service()
    warsaw = service._upsert_job(
        make_job(
            source="serpapi",
            external_id="g-waw",
            company="Dash0",
            role="Senior Frontend Engineer",
            location_text="Warsaw, Poland",
            canonical_url="https://careers.dash0.com/jobs/waw",
        )
    )
    berlin = service._upsert_job(
        make_job(
            source="serpapi",
            external_id="g-ber",
            company="Dash0",
            role="Senior Frontend Engineer",
            location_text="Berlin, Germany",
            canonical_url="https://careers.dash0.com/jobs/ber",
        )
    )
    assert warsaw[0] != berlin[0]
    assert _posting_count() == 2


def test_same_company_title_location_but_different_vacancy_stays_separate(temp_db):
    """Payments vs Growth teams at the same company must not merge."""
    service = _service()
    payments_jd = JD + " You will join the Payments team building checkout flows."
    growth_jd = (
        "We are looking for a Senior Frontend Engineer for the Growth team "
        "to run A/B experiments and build landing experiences with Next.js "
        "and Tailwind. Deep analytics instrumentation experience required. "
        "Hybrid in Warsaw."
    )
    payments = service._upsert_job(
        make_job(
            source="lever",
            external_id="pay-1",
            company="acmecorp",
            role="Senior Frontend Engineer",
            description=payments_jd,
            canonical_url="https://jobs.lever.co/acmecorp/pay-1",
        )
    )
    growth = service._upsert_job(
        make_job(
            source="lever",
            external_id="growth-1",
            company="acmecorp",
            role="Senior Frontend Engineer",
            description=growth_jd,
            canonical_url="https://jobs.lever.co/acmecorp/growth-1",
        )
    )
    assert payments[0] != growth[0]
    assert _posting_count() == 2
