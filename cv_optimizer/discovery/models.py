"""Normalized job model shared by every discovery source adapter."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class DiscoveredJob(BaseModel):
    """Provider-neutral canonical representation of a discovered vacancy.

    The matcher consumes `description` — never `raw_payload`.
    """

    source: str
    external_id: str

    company: str
    role: str
    description: str

    source_url: str | None = None
    apply_url: str | None = None
    canonical_url: str | None = None

    location_text: str | None = None

    work_model: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"

    remote_scope: Literal[
        "poland",
        "europe",
        "eu",
        "eea",
        "emea",
        "worldwide",
        "country_specific",
        "unknown",
    ] = "unknown"

    seniority: Literal[
        "intern",
        "junior",
        "mid",
        "senior",
        "staff",
        "lead",
        "principal",
        "unknown",
    ] = "unknown"

    employment_type: str | None = None

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_raw: str | None = None

    posted_at: datetime | None = None
    source_updated_at: datetime | None = None

    active_state: Literal["active", "inactive", "unknown"] = "unknown"
    active_confidence: Literal["high", "medium", "low"] = "low"

    raw_payload: dict[str, Any] | None = None

    def posted_at_iso(self) -> str | None:
        return self.posted_at.isoformat() if self.posted_at else None

    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class PrefilterResult(BaseModel):
    state: Literal["pass", "fail", "review"]
    reason: str


class DiscoveryQuery(BaseModel):
    """A single deterministic search query for a source."""

    q: str
    location: str | None = None
    remote: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class DiscoveryRunResult(BaseModel):
    """Outcome of one discovery run."""

    run_id: int
    status: str
    fetched: int = 0
    normalized: int = 0
    new: int = 0
    updated: int = 0
    filtered: int = 0
    scored: int = 0
    qualified: int = 0
    imported: int = 0
    linked_existing: int = 0
    errors: list[str] = Field(default_factory=list)
    imported_applications: list[dict] = Field(default_factory=list)
