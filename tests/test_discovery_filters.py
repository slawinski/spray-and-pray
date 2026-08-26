"""Cheap prefilter tests — all deterministic, no LLM calls."""

import pytest

from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.filters import prefilter
from cv_optimizer.discovery.models import DiscoveredJob

from conftest import make_job

LONG_JD = (
    "We are looking for a senior frontend engineer with strong product "
    "collaboration skills. You will build complex user interfaces with "
    "modern frameworks and TypeScript, own features end to end, work with "
    "designers and product managers, and ship high-quality software to "
    "production. 5+ years of experience required. Accessibility, testing, "
    "and performance are central to the role."
)


@pytest.fixture()
def config():
    return DiscoveryConfig()


def _prefilter(job, config) -> str:
    return prefilter(job, config).state


# ── PASS cases ───────────────────────────────────────────────────────────────

def test_warsaw_hybrid_senior_passes(config):
    job = make_job(
        role="Senior Frontend Engineer",
        location_text="Warsaw, Poland",
        work_model="hybrid",
    )
    assert _prefilter(job, config) == "pass"


def test_remote_europe_passes(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Remote — Europe",
        work_model="remote",
        remote_scope="europe",
    )
    assert _prefilter(job, config) == "pass"


def test_remote_worldwide_passes(config):
    job = make_job(
        role="Frontend Developer",
        location_text="Remote worldwide",
        work_model="remote",
        remote_scope="worldwide",
    )
    assert _prefilter(job, config) == "pass"


def test_angular_developer_remote_poland_passes(config):
    """Framework choice must never fail the prefilter."""
    job = make_job(
        role="Angular Developer",
        location_text="Remote — Poland",
        work_model="remote",
        remote_scope="poland",
    )
    assert _prefilter(job, config) == "pass"


def test_svelte_engineer_warsaw_passes(config):
    job = make_job(role="Svelte Engineer", location_text="Warsaw", work_model="hybrid")
    assert _prefilter(job, config) == "pass"


def test_unlevelled_frontend_role_passes(config):
    job = make_job(role="Frontend Engineer", seniority="unknown", description=LONG_JD)
    assert _prefilter(job, config) == "pass"


def test_vue_nuxt_solid_ember_never_fail_on_framework(config):
    for framework in ("Vue", "Nuxt", "Svelte", "Solid", "Ember", "SvelteKit", "Qwik", "Lit"):
        job = make_job(
            role=f"{framework} Developer",
            location_text="Warsaw",
            work_model="hybrid",
        )
        assert _prefilter(job, config) != "fail", framework


# ── FAIL cases ───────────────────────────────────────────────────────────────

def test_junior_react_developer_fails(config):
    job = make_job(role="Junior React Developer", seniority="junior")
    assert _prefilter(job, config) == "fail"


def test_frontend_intern_fails(config):
    job = make_job(role="Frontend Intern", seniority="intern")
    assert _prefilter(job, config) == "fail"


@pytest.mark.parametrize(
    "role",
    [
        "Python Backend Engineer",
        "Java Backend Engineer",
        "Data Engineer",
        "Data Scientist",
        "DevOps Engineer",
        "QA Engineer",
        "iOS Developer",
        "Android Developer",
        "Engineering Manager",
        "Product Manager",
        "UX Designer",
        "TypeScript Backend Engineer",
        "Backend Engineer (Angular)",
    ],
)
def test_irrelevant_families_fail(config, role):
    job = make_job(role=role, seniority="senior")
    assert _prefilter(job, config) == "fail", role


def test_new_york_onsite_fails(config):
    job = make_job(
        role="Senior Frontend Engineer",
        location_text="New York, NY",
        work_model="onsite",
    )
    assert _prefilter(job, config) == "fail"


def test_us_remote_only_fails(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Remote US only",
        work_model="remote",
    )
    assert _prefilter(job, config) == "fail"


def test_remote_canada_fails(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Remote Canada",
        work_model="remote",
    )
    assert _prefilter(job, config) == "fail"


def test_must_reside_in_california_fails(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Must reside in California",
        work_model="remote",
    )
    assert _prefilter(job, config) == "fail"


def test_short_jd_fails_before_anything_else(config):
    job = make_job(role="Senior Frontend Engineer", description="Too short.")
    assert _prefilter(job, config) == "fail"
    assert prefilter(job, config).reason == "insufficient_description"


def test_staff_and_lead_fail_by_default(config):
    for level, role in (("staff", "Staff Frontend Engineer"), ("lead", "Frontend Lead")):
        job = make_job(role=role, seniority=level)
        assert _prefilter(job, config) == "fail", role


# ── REVIEW cases ─────────────────────────────────────────────────────────────

def test_bare_remote_reviews(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Remote",
        work_model="remote",
        remote_scope="unknown",
    )
    assert _prefilter(job, config) == "review"


def test_work_from_anywhere_reviews(config):
    job = make_job(
        role="Frontend Engineer",
        location_text="Work from anywhere in your region",
        work_model="remote",
    )
    assert _prefilter(job, config) == "review"


def test_generic_software_engineer_without_signal_reviews(config):
    job = make_job(
        role="Software Engineer",
        seniority="unknown",
        description=(
            "We are looking for a software engineer to join our team. You "
            "will design, build, and maintain services, collaborate with "
            "other engineers, participate in code review, and improve our "
            "delivery processes. Strong communication skills required."
        ),
        location_text="Warsaw, Poland",
    )
    assert _prefilter(job, config) == "review"


def test_generic_software_engineer_with_frontend_signal_passes(config):
    job = make_job(
        role="Software Engineer",
        seniority="unknown",
        description=LONG_JD + " React frontend TypeScript web application",
        location_text="Warsaw, Poland",
    )
    assert _prefilter(job, config) == "pass"
