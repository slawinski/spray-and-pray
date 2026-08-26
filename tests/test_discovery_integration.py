"""End-to-end discovery orchestration tests.

Uses a fake source and a mocked LLM analyzer — zero live network calls.
Covers: caching, threshold import, prefilter-before-LLM, provider
isolation, rate limiting, preview/no-import modes, rescore, lifecycle,
and run persistence.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cv_optimizer import db
from cv_optimizer.config import settings
from cv_optimizer.discovery import lock as lock_mod
from cv_optimizer.discovery import notify as notify_mod
from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.models import DiscoveredJob, DiscoveryQuery
from cv_optimizer.discovery.service import DiscoveryService
from cv_optimizer.discovery.sources import RateLimited, SourceError
from cv_optimizer.matching import MatchAnalyzer, MatchRequirement, RawMatchAnalysis

from conftest import make_job

STRONG_JD = (
    "REQUIREMENT_STRONG: We are looking for a Senior Frontend Engineer to "
    "build complex user interfaces with React and TypeScript. Strong product "
    "collaboration, accessibility, and design systems experience required. "
    "5+ years of frontend engineering experience. Hybrid work model with an "
    "office in Warsaw, Poland."
)

WEAK_JD = (
    "REQUIREMENT_WEAK: We need a frontend engineer who is also an expert in "
    "Java backend development. The role requires 5+ years of React and deep "
    "Java Spring expertise. Hybrid in Warsaw, Poland."
)

SHORT_JD = "Too short."

US_ONLY_JD = (
    "We are looking for a Frontend Engineer in San Francisco. You must "
    "reside in the United States. React and TypeScript required. Remote US "
    "only. Five plus years of experience building web applications with "
    "React, accessibility and testing."
)


class FakeSource:
    name = "serpapi"

    def __init__(self, jobs: list[DiscoveredJob] | None = None, *, fail_with: Exception | None = None, fail_after: int = 0):
        self.jobs = jobs or []
        self.fail_with = fail_with
        self.fail_after = fail_after
        self.calls = 0

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]:
        self.calls += 1
        if self.fail_with is not None and self.calls > self.fail_after:
            raise self.fail_with
        return list(self.jobs)


def _small_config(**overrides) -> DiscoveryConfig:
    kwargs = {
        "roles": ["frontend engineer"],
        "locations": {
            "warsaw": {"onsite": True, "hybrid": True},
            "remote": {"poland": True, "europe": False, "eu": False, "eea": False, "emea": False, "worldwide": False},
        },
        "sources": {
            "serpapi": {"enabled": True, "max_pages_per_query": 1},
            "lever": {"enabled": False, "sites": []},
            "ashby": {"enabled": False, "boards": []},
            "greenhouse": {"enabled": False, "boards": []},
        },
    }
    kwargs.update(overrides)
    return DiscoveryConfig(**kwargs)


def _strong_analysis() -> RawMatchAnalysis:
    return RawMatchAnalysis(
        role_family="frontend",
        target_seniority="senior",
        requirements=[
            MatchRequirement(id="r1", requirement="Frontend engineering", category="role_scope", priority="must", is_core=True, evidence_level="direct", evidence_paths=["/skills/frameworks_and_libraries/0"], rationale="x"),
            MatchRequirement(id="r2", requirement="React", category="technical", priority="must", is_core=True, evidence_level="direct", evidence_paths=["/skills/frameworks_and_libraries/0"], rationale="x"),
            MatchRequirement(id="r3", requirement="5+ years experience", category="experience_delivery", priority="must", is_core=True, evidence_level="direct", evidence_paths=["/experience/0/achievements/0"], rationale="x"),
        ],
        eligibility=[],
    )


def _weak_analysis() -> RawMatchAnalysis:
    return RawMatchAnalysis(
        role_family="frontend",
        target_seniority="senior",
        requirements=[
            MatchRequirement(id="r1", requirement="Frontend engineering", category="role_scope", priority="must", is_core=True, evidence_level="direct", evidence_paths=["/skills/frameworks_and_libraries/0"], rationale="x"),
            MatchRequirement(id="r2", requirement="Java", category="technical", priority="must", is_core=True, evidence_level="none", evidence_paths=[], rationale="absent"),
            MatchRequirement(id="r3", requirement="5+ years experience", category="experience_delivery", priority="must", is_core=True, evidence_level="direct", evidence_paths=["/experience/0/achievements/0"], rationale="x"),
        ],
        eligibility=[],
    )


@pytest.fixture()
def mock_llm(monkeypatch):
    calls: list[str] = []

    def fake_analyze(self, jd_text: str, profile: dict) -> RawMatchAnalysis:
        calls.append(jd_text)
        if "REQUIREMENT_WEAK" in jd_text:
            return _weak_analysis()
        return _strong_analysis()

    monkeypatch.setattr(MatchAnalyzer, "analyze", fake_analyze)
    return calls


@pytest.fixture()
def mock_notify(monkeypatch):
    notifications: list[list] = []
    monkeypatch.setattr(notify_mod, "notify_new_imports", lambda imported: notifications.append(imported))
    return notifications


def _service(config, source) -> DiscoveryService:
    service = DiscoveryService(config=config)
    service.build_sources = lambda source_filter=None: [source]  # type: ignore[method-assign]
    return service


def _job(**kwargs) -> DiscoveredJob:
    external_id = kwargs.pop("external_id", "job-1")
    return make_job(
        source="serpapi",
        external_id=external_id,
        description=kwargs.pop("description", STRONG_JD),
        canonical_url=kwargs.pop("canonical_url", f"https://careers.example.com/jobs/{external_id}"),
        posted_at=kwargs.pop("posted_at", datetime.now(timezone.utc) - timedelta(days=1)),
        **kwargs,
    )


# ── Full pipeline ────────────────────────────────────────────────────────────

def test_full_run_imports_qualifying_job(temp_db, temp_apps_dir, master_cv, mock_llm, mock_notify):
    config = _small_config()
    source = FakeSource([_job(external_id="a", company="Dash0", role="Senior Frontend Engineer")])
    service = _service(config, source)

    result = service.run()

    assert result.status == "completed"
    assert result.fetched >= 1
    assert result.new == 1
    assert result.scored == 1
    assert result.qualified == 1
    assert result.imported == 1

    apps = db.list_applications_with_status()
    assert len(apps) == 1
    app = apps[0]
    assert app["latest_status"] == "draft"
    assert app["source"] == "auto:serpapi"
    assert app["jd_path"] and Path(app["jd_path"]).exists()
    assert app["cv_path"] is None
    assert app["cover_letter_path"] is None

    run = db.get_discovery_run(result.run_id)
    assert run["status"] == "completed"
    assert run["imported_count"] == 1
    assert mock_notify  # exactly one batched notification
    assert len(mock_notify) == 1
    assert len(mock_notify[0]) == 1


def test_below_threshold_job_stays_in_discovery_only(temp_db, temp_apps_dir, master_cv, mock_llm, mock_notify):
    config = _small_config()
    source = FakeSource([_job(external_id="weak", description=WEAK_JD)])
    service = _service(config, source)

    result = service.run()

    assert result.scored == 1
    assert result.qualified == 0
    assert result.imported == 0
    assert len(db.list_applications()) == 0
    assert mock_notify == []  # no notification when nothing imported

    # The job persists with its score for future reconsideration (Role D).
    posting = db.get_job_posting_by_source_id("serpapi", "weak")
    assert posting is not None
    assert posting["latest_match_score"] < 85
    assert posting["match_state"] == "scored"


def test_us_only_job_filtered_before_llm(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([
        _job(external_id="us-only", description=US_ONLY_JD, location_text="Remote US only", work_model="remote")
    ])
    service = _service(config, source)

    result = service.run()

    posting = db.get_job_posting_by_source_id("serpapi", "us-only")
    assert posting["prefilter_state"] == "fail"
    assert mock_llm == []  # never scored
    assert result.scored == 0
    assert len(db.list_applications()) == 0


def test_short_jd_rejected_before_llm(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="short", description=SHORT_JD)])
    service = _service(config, source)

    service.run()

    posting = db.get_job_posting_by_source_id("serpapi", "short")
    assert posting["prefilter_state"] == "fail"
    assert posting["prefilter_reason"] == "insufficient_description"
    assert mock_llm == []


# ── Caching ──────────────────────────────────────────────────────────────────

def test_unchanged_jd_reuses_cached_assessment(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="same", description=STRONG_JD)])
    service = _service(config, source)

    first = service.run()
    llm_calls_after_first = len(mock_llm)
    assert first.scored == 1
    assert llm_calls_after_first == 1

    second = service.run()
    assert len(mock_llm) == llm_calls_after_first  # zero additional LLM calls
    assert second.imported == 0  # already imported

    assessments = db.get_latest_job_match(
        db.get_job_posting_by_source_id("serpapi", "same")["id"]
    )
    assert assessments is not None


def test_changed_jd_creates_new_assessment(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="changed", description=STRONG_JD)])
    service = _service(config, source)
    service.run(import_matches=False)
    assert len(mock_llm) == 1

    new_jd = STRONG_JD + " We are now also using GraphQL extensively for data fetching."
    source.jobs = [_job(external_id="changed", description=new_jd)]
    service.run(import_matches=False)

    assert len(mock_llm) == 2
    posting = db.get_job_posting_by_source_id("serpapi", "changed")
    assert "GraphQL" in posting["description"]


def test_changed_master_cv_invalidates_cache(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="cv-change")])
    service = _service(config, source)
    service.run(import_matches=False)
    assert len(mock_llm) == 1

    cv = json.loads(Path(master_cv).read_text())
    cv["skills"]["frameworks_and_libraries"].append("SolidStart")
    Path(master_cv).write_text(json.dumps(cv))

    service.run(import_matches=False)
    assert len(mock_llm) == 2  # new candidate hash → fresh assessment


def test_match_version_change_invalidates_cache(temp_db, temp_apps_dir, master_cv, mock_llm, monkeypatch):
    config = _small_config()
    source = FakeSource([_job(external_id="version-change")])
    service = _service(config, source)
    service.run(import_matches=False)
    assert len(mock_llm) == 1

    monkeypatch.setattr(settings, "match_scoring_version", "match-v3-experimental")
    service.run(import_matches=False)
    assert len(mock_llm) == 2


# ── Modes ────────────────────────────────────────────────────────────────────

def test_preview_mode_has_no_llm_and_no_import(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="preview")])
    service = _service(config, source)

    result = service.run(preview=True)

    assert mock_llm == []
    assert result.scored == 0
    assert result.imported == 0
    assert len(db.list_applications()) == 0
    posting = db.get_job_posting_by_source_id("serpapi", "preview")
    assert posting is not None  # persisted + prefilted
    assert posting["prefilter_state"] == "pass"
    assert posting["match_state"] == "pending"


def test_no_import_mode_scores_but_does_not_import(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="no-import")])
    service = _service(config, source)

    result = service.run(import_matches=False)

    assert len(mock_llm) == 1
    assert result.scored == 1
    assert result.imported == 0
    assert len(db.list_applications()) == 0
    posting = db.get_job_posting_by_source_id("serpapi", "no-import")
    assert posting["latest_match_score"] >= 85
    assert posting["user_state"] == "pending"

    # A later normal run imports from the backlog without new LLM calls.
    result2 = service.run()
    assert len(mock_llm) == 1
    assert result2.imported == 1
    assert len(db.list_applications()) == 1


def test_rescore_forces_fresh_assessment(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="rescore")])
    service = _service(config, source)
    service.run(import_matches=False)
    assert len(mock_llm) == 1

    service.run(import_matches=False, force_rescore=True)
    assert len(mock_llm) == 2


# ── Reliability ──────────────────────────────────────────────────────────────

def test_provider_failure_does_not_kill_run(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    broken = FakeSource(fail_with=SourceError("serpapi: connection refused"), fail_after=0)
    service = _service(config, broken)

    result = service.run()

    assert result.status in ("completed", "completed_with_errors")
    assert any("serpapi" in e for e in result.errors)
    run = db.get_discovery_run(result.run_id)
    assert run["status"] in ("completed", "completed_with_errors")
    assert json.loads(run["errors_json"])


def test_rate_limited_source_stops_but_run_continues(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    limited = FakeSource(fail_with=RateLimited("serpapi: rate limited (HTTP 429)"), fail_after=1)
    service = _service(config, limited)

    result = service.run()

    # No busy-loop: the source made at most 2 calls, then stopped.
    assert limited.calls <= 2
    assert any("429" in e for e in result.errors)


def test_one_llm_failure_does_not_stop_other_jobs(temp_db, temp_apps_dir, master_cv, mock_llm, monkeypatch):
    config = _small_config()
    jobs = [
        _job(external_id="good"),
        _job(external_id="flaky", description=WEAK_JD),
    ]
    source = FakeSource(jobs)
    service = _service(config, source)

    mock_analyze = MatchAnalyzer.analyze  # fixture fake, records into mock_llm

    def flaky_analyze(self, jd_text, profile):
        if "REQUIREMENT_WEAK" in jd_text:
            raise ValueError("LLM timeout")
        return mock_analyze(self, jd_text, profile)

    monkeypatch.setattr(MatchAnalyzer, "analyze", flaky_analyze)

    result = service.run()

    assert result.status == "completed_with_errors"
    assert result.imported == 1  # the healthy job still imported
    flaky = db.get_job_posting_by_source_id("serpapi", "flaky")
    assert flaky["match_state"] == "error"

    # A future run retries the errored job.
    llm_calls_before = len(mock_llm)
    monkeypatch.setattr(MatchAnalyzer, "analyze", mock_analyze)
    service.run()
    assert len(mock_llm) > llm_calls_before  # the errored job was re-analyzed


def test_import_failure_leaves_retryable_posting(temp_db, temp_apps_dir, master_cv, mock_llm, monkeypatch):
    config = _small_config()
    source = FakeSource([_job(external_id="import-fail")])
    service = _service(config, source)

    def boom(job_posting_id):
        raise RuntimeError("import exploded")

    monkeypatch.setattr(service.importer, "import_job", boom)

    result = service.run()

    assert result.status == "completed_with_errors"
    assert len(db.list_applications()) == 0
    posting = db.get_job_posting_by_source_id("serpapi", "import-fail")
    assert posting["user_state"] == "pending"
    assert posting["application_id"] is None


def test_existing_manual_application_links_not_duplicates(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    # The user already tracked this vacancy manually.
    manual_id = db.insert_application(
        "Dash0", "Senior Frontend Engineer",
        job_url="https://careers.example.com/jobs/manual-dup",
    )
    db.insert_status(manual_id, "draft")

    source = FakeSource([_job(external_id="manual-dup", company="Dash0", role="Senior Frontend Engineer")])
    service = _service(config, source)

    result = service.run()

    assert len(db.list_applications()) == 1
    posting = db.get_job_posting_by_source_id("serpapi", "manual-dup")
    assert posting["application_id"] == manual_id
    assert posting["user_state"] == "imported"
    assert result.linked_existing == 1
    assert result.imported == 0  # no NEW application created


def test_dismissed_posting_not_reimported(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([_job(external_id="dismiss-me")])
    service = _service(config, source)

    first = service.run()
    assert first.imported == 1
    app_id = db.list_applications_with_status()[0]["id"]

    from cv_optimizer.tracker import remove_application

    remove_application(app_id)

    second = service.run()
    assert second.imported == 0
    assert len(db.list_applications()) == 0
    posting = db.get_job_posting_by_source_id("serpapi", "dismiss-me")
    assert posting["user_state"] == "dismissed"


# ── Scoring budget ───────────────────────────────────────────────────────────

def test_max_scores_caps_llm_usage(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config(max_scores_per_run=2)
    jobs = [
        _job(external_id=f"budget-{i}",
             company=f"Employer {i}",
             posted_at=datetime.now(timezone.utc) - timedelta(days=i))
        for i in range(5)
    ]
    source = FakeSource(jobs)
    service = _service(config, source)

    result = service.run()

    assert len(mock_llm) == 2
    assert result.scored == 2
    # The rest remain pending, not discarded.
    for i in range(2, 5):
        posting = db.get_job_posting_by_source_id("serpapi", f"budget-{i}")
        assert posting["match_state"] == "pending"

    # A later run scores the remainder.
    service.run(max_scores=10)
    assert len(mock_llm) == 5


def test_budget_caps_cache_misses_after_cv_change(temp_db, temp_apps_dir, master_cv, mock_llm):
    """A Master CV change invalidates every cache. Jobs that were already
    scored must NOT trigger unbounded LLM calls outside the budget."""
    config = _small_config(max_scores_per_run=2)
    jobs = [
        _job(external_id=f"cv-{i}", company=f"Employer {i}") for i in range(4)
    ]
    source = FakeSource(jobs)
    service = _service(config, source)

    # Score all four with a generous budget, without importing.
    service.run(import_matches=False, max_scores=10)
    assert len(mock_llm) == 4

    # Change the Master CV → all cache identities invalidated.
    cv = json.loads(Path(master_cv).read_text())
    cv["skills"]["frameworks_and_libraries"].append("SolidStart")
    Path(master_cv).write_text(json.dumps(cv))

    # Next run has a small budget: at most 2 fresh LLM calls, and the
    # cache-missed rows are returned to 'pending' rather than leaked.
    result = service.run(import_matches=False, max_scores=2)
    assert len(mock_llm) == 6  # 4 + exactly 2 budgeted re-scores
    assert result.scored == 2

    pending = 0
    for i in range(4):
        posting = db.get_job_posting_by_source_id("serpapi", f"cv-{i}")
        if posting["match_state"] == "pending":
            pending += 1
    assert pending == 2


def test_prioritization_orders_high_confidence_first(temp_db):
    """§31: newest first, then active confidence, then prefilter pass."""
    config = _small_config()
    service = _service(config, FakeSource([]))
    now = datetime.now(timezone.utc)
    postings = []
    for i, (confidence, pref) in enumerate(
        [("low", "review"), ("high", "pass"), ("medium", "review"), ("high", "review")]
    ):
        pid = db.insert_job_posting(
            company=f"Co {i}", role="Senior Frontend Engineer",
            description=STRONG_JD, description_hash=f"h{i}",
            canonical_url=f"https://co{i}.example/job",
            posted_at=(now - timedelta(days=i)).isoformat(),
            active_state="active", active_confidence=confidence,
            company_norm=f"co {i}", role_norm="senior frontend engineer",
            location_norm="warsaw poland",
        )
        db.set_job_prefilter(pid, pref, None)
        postings.append((pid, confidence, pref))

    ordered = service._prioritize({p[0] for p in postings}, force_rescore=False)
    # Newest first.
    assert ordered[0]["id"] == postings[0][0]
    # Among equal-age ties, high confidence beats low, pass beats review.
    confidences = [r["active_confidence"] for r in ordered]
    # With strictly decreasing ages, the primary key dominates; verify the
    # secondary ordering by comparing two same-age rows directly.
    pid_a = db.insert_job_posting(
        company="TieCo A", role="Senior Frontend Engineer",
        description=STRONG_JD, description_hash="ha",
        canonical_url="https://tiea.example/job",
        posted_at=(now - timedelta(days=1)).isoformat(),
        active_state="active", active_confidence="low",
        company_norm="tieco a", role_norm="senior frontend engineer",
        location_norm="warsaw poland",
    )
    db.set_job_prefilter(pid_a, "review", None)
    pid_b = db.insert_job_posting(
        company="TieCo B", role="Senior Frontend Engineer",
        description=STRONG_JD, description_hash="hb",
        canonical_url="https://tieb.example/job",
        posted_at=(now - timedelta(days=1)).isoformat(),
        active_state="active", active_confidence="high",
        company_norm="tieco b", role_norm="senior frontend engineer",
        location_norm="warsaw poland",
    )
    db.set_job_prefilter(pid_b, "pass", None)
    ordered = service._prioritize({pid_a, pid_b}, force_rescore=False)
    assert ordered[0]["id"] == pid_b  # high confidence beats low at same age


def test_linked_existing_is_not_counted_as_new_import(temp_db, temp_apps_dir, master_cv, mock_llm, mock_notify):
    config = _small_config()
    manual_id = db.insert_application(
        "Dash0", "Senior Frontend Engineer",
        job_url="https://careers.example.com/jobs/linked",
    )
    db.insert_status(manual_id, "draft")
    source = FakeSource([_job(external_id="linked")])
    service = _service(config, source)

    result = service.run()

    assert result.imported == 0
    assert result.linked_existing == 1
    assert mock_notify == []  # no "new jobs" notification for a mere link


# ── Concurrency lock ─────────────────────────────────────────────────────────

def test_concurrent_discovery_prevented(tmp_path):
    lock_path = tmp_path / ".discovery.lock"
    first = lock_mod.DiscoveryLock(lock_path)
    second = lock_mod.DiscoveryLock(lock_path)

    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_lock_context_manager_raises_when_held(tmp_path):
    lock_path = tmp_path / ".discovery.lock"
    first = lock_mod.DiscoveryLock(lock_path)
    assert first.acquire()
    with pytest.raises(lock_mod.DiscoveryLockError):
        with lock_mod.DiscoveryLock(lock_path):
            pass
    first.release()


# ── Run persistence ──────────────────────────────────────────────────────────

def test_run_records_source_stats_and_counts(temp_db, temp_apps_dir, master_cv, mock_llm):
    config = _small_config()
    source = FakeSource([
        _job(external_id="stats-1", company="Employer A"),
        _job(external_id="stats-2", company="Employer B", description=WEAK_JD),
    ])
    service = _service(config, source)

    result = service.run()

    run = db.get_discovery_run(result.run_id)
    assert run["fetched_count"] >= 2
    assert run["new_count"] == 2
    assert run["scored_count"] == 2
    assert run["imported_count"] == 1
    stats = json.loads(run["source_stats_json"])
    assert stats["serpapi"]["fetched"] >= 2
    assert stats["serpapi"]["new"] == 2
