"""Match-score backfill tests (score_missing_applications) — mocked LLM."""

import json
from pathlib import Path

from cv_optimizer import db
from cv_optimizer.matching import MatchAnalyzer, MatchRequirement, MatchService, RawMatchAnalysis

JD_TEXT = (
    "We are looking for a Senior Frontend Engineer to build complex user "
    "interfaces with React and TypeScript. Strong product collaboration, "
    "accessibility, and design systems experience required. 5+ years of "
    "frontend engineering experience. Hybrid work model with an office in "
    "Warsaw, Poland."
)


def _fake_analysis() -> RawMatchAnalysis:
    return RawMatchAnalysis(
        role_family="frontend",
        target_seniority="senior",
        requirements=[
            MatchRequirement(
                id="r1", requirement="React", category="technical",
                priority="must", is_core=True, evidence_level="direct",
                evidence_paths=["/skills/frameworks_and_libraries/0"], rationale="x",
            ),
        ],
        eligibility=[],
    )


def _app_with_jd(tmp_path, company: str, role: str = "Frontend Engineer", jd_text: str = JD_TEXT) -> int:
    jd_file = tmp_path / f"{company}-jd.txt"
    jd_file.write_text(jd_text, encoding="utf-8")
    return db.insert_application(company, role, jd_path=str(jd_file))


def test_backfills_only_missing_applications(temp_db, temp_apps_dir, master_cv, tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(MatchAnalyzer, "analyze", lambda self, jd, profile: (calls.append(jd) or _fake_analysis()))

    a1 = _app_with_jd(tmp_path, "Alpha")
    a2 = _app_with_jd(tmp_path, "Beta")
    a3 = db.insert_application("Gamma", "No JD")  # no jd_path
    a4 = _app_with_jd(tmp_path, "Delta")
    db.insert_match_assessment(
        a4, 77, "GOOD", "HIGH", 77.0, json.dumps({"x": 1}),
        "old-candidate-hash", "old-jd-hash", "match-v1", "match-prompt-v1", "old-model",
    )

    result = MatchService().score_missing_applications()

    assert result["scored"] == 2  # Alpha + Beta only
    assert result["skipped_no_jd"] == 1  # Gamma
    assert result["errors"] == []
    assert len(calls) == 2  # Delta's existing assessment not re-scored

    for app_id in (a1, a2):
        match = db.get_latest_match(app_id)
        assert match is not None
        assert match["scoring_version"] == "match-v2"
    # Delta keeps its historical match-v1 assessment.
    delta_match = db.get_latest_match(a4)
    assert delta_match["score"] == 77
    assert delta_match["scoring_version"] == "match-v1"


def test_force_rescores_everything_with_jd(temp_db, temp_apps_dir, master_cv, tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(MatchAnalyzer, "analyze", lambda self, jd, profile: (calls.append(jd) or _fake_analysis()))

    a1 = _app_with_jd(tmp_path, "Alpha")
    db.insert_match_assessment(
        a1, 50, "WEAK", "HIGH", 50.0, "{}", "h1", "h2", "match-v1", "p1", "m1",
    )

    result = MatchService().score_missing_applications(force=True)

    assert result["scored"] == 1
    assert len(calls) == 1  # fresh LLM call despite existing (v1) assessment
    assert db.get_latest_match(a1)["scoring_version"] == "match-v2"
    assert len([r for r in db._connect().execute(
        "SELECT id FROM match_assessments WHERE application_id = ?", (a1,)
    )]) == 2  # history preserved, new row appended


def test_one_failure_does_not_stop_the_batch(temp_db, temp_apps_dir, master_cv, tmp_path, monkeypatch):
    def flaky(self, jd, profile):
        if "Beta" in jd:
            raise ValueError("LLM timeout")
        return _fake_analysis()

    monkeypatch.setattr(MatchAnalyzer, "analyze", flaky)

    a1 = _app_with_jd(tmp_path, "Alpha")
    a2 = _app_with_jd(tmp_path, "Beta", jd_text=JD_TEXT.replace("React", "Beta-stack"))

    result = MatchService().score_missing_applications()

    assert result["scored"] == 1
    assert len(result["errors"]) == 1
    assert "Beta" in result["errors"][0]
    assert db.get_latest_match(a1) is not None
    assert db.get_latest_match(a2) is None
