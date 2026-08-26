"""Shared test configuration for the discovery + matching test suites."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jobs"


def load_fixture(name: str) -> dict | list:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Isolated SQLite database for the duration of one test."""
    import cv_optimizer.db as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


@pytest.fixture()
def temp_apps_dir(tmp_path, monkeypatch):
    """Isolated applications/ directory."""
    from cv_optimizer import tracker

    apps_dir = tmp_path / "applications"
    monkeypatch.setattr(tracker, "APPLICATIONS_DIR", apps_dir)
    return apps_dir


@pytest.fixture()
def master_cv(tmp_path, monkeypatch):
    """A minimal Master CV (React/Vue/Next experience, Warsaw, no Angular)."""
    from cv_optimizer.config import settings

    cv = {
        "personal_info": {"name": "Test Candidate", "location": "Warsaw, Poland"},
        "summary": "Frontend engineer with React, Vue, and Next.js experience.",
        "skills": {
            "languages": ["TypeScript", "JavaScript"],
            "frameworks_and_libraries": ["React", "Next.js", "Vue.js", "Preact"],
            "tools_and_infrastructure": ["Vitest", "Storybook"],
            "soft_skills": ["communication"],
        },
        "experience": [
            {
                "company": "Example",
                "role": "Senior Frontend Engineer",
                "achievements": ["Shipped a React design system"],
            }
        ],
        "speaking_and_community": [],
        "education": [],
        "certifications": [],
        "languages": [
            {"language": "Polish", "proficiency": "Native"},
            {"language": "English", "proficiency": "Full professional"},
        ],
    }
    cv_path = tmp_path / "master_cv.json"
    cv_path.write_text(json.dumps(cv), encoding="utf-8")
    monkeypatch.setattr(settings, "master_cv_path", str(cv_path))
    return cv_path


@pytest.fixture()
def discovery_config():
    from cv_optimizer.discovery.config import DiscoveryConfig

    return DiscoveryConfig()


def make_job(
    *,
    source: str = "serpapi",
    external_id: str = "job-1",
    company: str = "Dash0",
    role: str = "Senior Frontend Engineer",
    description: str | None = None,
    location_text: str | None = "Warsaw, Poland",
    work_model: str = "hybrid",
    remote_scope: str = "unknown",
    seniority: str = "senior",
    apply_url: str | None = None,
    canonical_url: str | None = None,
    posted_at=None,
    active_state: str = "unknown",
    active_confidence: str = "medium",
    **kwargs,
):
    from cv_optimizer.discovery.models import DiscoveredJob

    if description is None:
        description = (
            "We are looking for a Senior Frontend Engineer to build complex "
            "user interfaces with React and TypeScript. Strong product "
            "collaboration, accessibility, and design systems experience "
            "required. 5+ years of frontend engineering experience. Hybrid "
            "work model with an office in Warsaw, Poland."
        )
    return DiscoveredJob(
        source=source,
        external_id=external_id,
        company=company,
        role=role,
        description=description,
        location_text=location_text,
        work_model=work_model,
        remote_scope=remote_scope,
        seniority=seniority,
        apply_url=apply_url,
        canonical_url=canonical_url,
        posted_at=posted_at,
        active_state=active_state,
        active_confidence=active_confidence,
        **kwargs,
    )
