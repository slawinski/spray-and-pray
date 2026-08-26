"""Source adapter tests — fixture JSON → DiscoveredJob. No live network calls."""

import pytest

from cv_optimizer.discovery.sources import (
    AshbySource,
    GreenhouseSource,
    LeverSource,
    SerpApiSource,
)

from conftest import load_fixture


# ── SerpApi ──────────────────────────────────────────────────────────────────

def test_serpapi_normalization():
    fixture = load_fixture("serpapi.json")
    source = SerpApiSource(api_key="test-key-not-used")
    jobs = source.normalize_page(fixture)
    assert len(jobs) == 4

    first = jobs[0]
    assert first.source == "serpapi"
    assert first.external_id == "serp-dash0-sfe"
    assert first.company == "Dash0"
    assert first.role == "Senior Frontend Engineer"
    assert "Senior Frontend Engineer" in first.description
    assert "React" in first.description
    assert first.location_text == "Warsaw, Poland"
    assert first.posted_at is not None  # "3 days ago" parsed
    assert first.apply_url == "https://careers.dash0.com/jobs/senior-frontend-engineer?utm_source=google_jobs&gh_src=abc"
    assert first.employment_type == "Full-time"
    # Tracking params stripped from the canonical URL.
    assert first.canonical_url == "https://careers.dash0.com/jobs/senior-frontend-engineer"


def test_serpapi_remote_europe_scope():
    fixture = load_fixture("serpapi.json")
    source = SerpApiSource(api_key="x")
    jobs = source.normalize_page(fixture)
    remote = jobs[3]
    assert remote.work_model == "remote"
    assert remote.remote_scope == "europe"


def test_serpapi_requires_api_key():
    source = SerpApiSource(api_key="")
    with pytest.raises(Exception) as exc:
        source.fetch(__import__("cv_optimizer.discovery.models", fromlist=["DiscoveryQuery"]).DiscoveryQuery(q="x"))
    assert "SERPAPI_API_KEY" in str(exc.value)


# ── Lever ────────────────────────────────────────────────────────────────────

def test_lever_normalization():
    fixture = load_fixture("lever.json")
    source = LeverSource(sites=["acmecorp"])
    jobs = [source.normalize_job(raw, site="acmecorp") for raw in fixture]
    assert len(jobs) == 2

    first = jobs[0]
    assert first.source == "lever"
    assert first.external_id == "a3f2c1d0-9e6f-4b5a-9c1d-2e3f4a5b6c7d"
    assert first.role == "Senior Product Engineer"
    assert first.company == "acmecorp"
    assert "React" in first.description
    assert first.location_text == "Warsaw, Poland"
    assert first.work_model == "hybrid"
    assert first.active_state == "active"
    assert first.active_confidence == "high"
    assert first.employment_type == "Full-time"
    assert first.canonical_url == "https://jobs.lever.co/acmecorp/a3f2c1d0-9e6f-4b5a-9c1d-2e3f4a5b6c7d"
    assert first.posted_at is not None

    second = jobs[1]
    assert second.role == "Angular Developer"
    assert second.work_model == "remote"
    assert second.remote_scope == "poland"


# ── Ashby ────────────────────────────────────────────────────────────────────

def test_ashby_normalization():
    fixture = load_fixture("ashby.json")
    source = AshbySource(boards=["exampleco"])
    jobs = [source.normalize_job(raw, board="exampleco") for raw in fixture["jobs"]]
    assert len(jobs) == 2

    first = jobs[0]
    assert first.source == "ashby"
    assert first.external_id == "ashby-001"
    assert first.role == "Senior Svelte Engineer"
    assert "Svelte" in first.description
    assert first.work_model == "remote"
    assert first.remote_scope == "europe"
    assert first.salary_raw == "€80k–€110k / year"
    assert first.salary_min == 80000
    assert first.salary_max == 110000
    assert first.salary_currency == "EUR"
    assert first.posted_at is not None

    second = jobs[1]
    assert second.work_model == "hybrid"
    assert second.salary_currency == "PLN"


# ── Greenhouse ───────────────────────────────────────────────────────────────

def test_greenhouse_rate_limit_propagates(monkeypatch):
    """HTTP 429 on the detail endpoint must stop the provider, not loop."""
    from cv_optimizer.discovery.sources.base import RateLimited

    board_list = load_fixture("greenhouse.json")
    detail = load_fixture("greenhouse_job.json")
    source = GreenhouseSource(boards=["exampleai"])
    calls = []

    def fake_get_json(url, *, params=None):
        calls.append(url)
        if "jobs/424243" in url:
            raise RateLimited("greenhouse: rate limited (HTTP 429)")
        if "jobs/424242" in url:
            return detail
        return board_list

    monkeypatch.setattr(source, "_get_json", fake_get_json)

    with pytest.raises(RateLimited):
        source.fetch(
            __import__("cv_optimizer.discovery.models", fromlist=["DiscoveryQuery"]).DiscoveryQuery(q="x")
        )
    # Board list + first detail + 429 → no further detail requests.
    assert len(calls) == 3
    assert calls[-1].endswith("jobs/424243")


def test_greenhouse_normalization(monkeypatch):
    board_list = load_fixture("greenhouse.json")
    detail = load_fixture("greenhouse_job.json")

    source = GreenhouseSource(boards=["exampleai"])

    second_detail = {
        **board_list["jobs"][1],
        "content": (
            "<p>We are hiring a Senior Web Engineer for our Warsaw office. "
            "You will build modern web applications with <strong>Vue</strong> "
            "and TypeScript, improve performance, and mentor engineers.</p>"
        ),
    }

    def fake_get_json(url, *, params=None):
        if "jobs/424242" in url:
            return detail
        if "jobs/424243" in url:
            return second_detail
        return board_list

    monkeypatch.setattr(source, "_get_json", fake_get_json)
    jobs = source.fetch(
        __import__("cv_optimizer.discovery.models", fromlist=["DiscoveryQuery"]).DiscoveryQuery(q="product engineer")
    )
    assert len(jobs) == 2

    first = jobs[0]
    assert first.source == "greenhouse"
    assert first.external_id == "424242"
    assert first.role == "Product Engineer"
    assert "TypeScript" in first.description
    assert "<strong>" not in first.description  # HTML stripped
    assert first.remote_scope == "emea"
    assert first.active_state == "active"
    assert first.canonical_url == "https://boards.greenhouse.io/exampleai/jobs/424242"

    second = jobs[1]
    assert second.external_id == "424243"
    assert "Vue" in second.description
