"""Ashby public Job Posting API adapter.

GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
"""

import logging

from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.models import DiscoveredJob, DiscoveryQuery
from cv_optimizer.discovery.sources.base import (
    HttpJobSource,
    SourceError,
    classify_remote_scope,
    classify_seniority_title,
    classify_work_model,
    clean_text,
    default_canonical_url,
    parse_posted_at,
    parse_salary,
)

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class AshbySource(HttpJobSource):
    name = "ashby"

    def __init__(self, boards: list[str], *, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.boards = [b.strip().rstrip("/") for b in boards if b and b.strip()]

    @classmethod
    def from_config(cls, config: DiscoveryConfig) -> "AshbySource":
        cfg = config.boards_for("ashby")
        return cls(boards=cfg.boards or cfg.sites)

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]:
        if not self.boards:
            logger.info("ashby: no boards configured; skipping")
            return []
        jobs: list[DiscoveredJob] = []
        for board in self.boards:
            url = ENDPOINT.format(board=board)
            data = self._get_json(url, params={"includeCompensation": "true"})
            if not isinstance(data, dict):
                raise SourceError(f"ashby: unexpected response shape for {board}")
            for raw in data.get("jobs") or []:
                job = self.normalize_job(raw, board=board)
                if job is not None:
                    jobs.append(job)
        return jobs

    def normalize_job(self, raw: dict, *, board: str) -> DiscoveredJob | None:
        title = clean_text(raw.get("title") or "")
        if not title:
            return None
        external_id = str(raw.get("id") or "")
        if not external_id:
            return None

        description = clean_text(raw.get("descriptionPlain") or "")

        location = clean_text(raw.get("location") or "")
        secondary = raw.get("secondaryLocations") or []
        secondary_texts = [clean_text(s.get("location") or "") for s in secondary]
        secondary_texts = [t for t in secondary_texts if t]
        if secondary_texts:
            location = "; ".join([location] + secondary_texts) if location else "; ".join(secondary_texts)

        is_remote = bool(raw.get("isRemote")) or any(
            s.get("isRemote") for s in secondary
        )
        workplace_type = raw.get("workplaceType") or None
        work_model = classify_work_model(location, workplace_type=workplace_type, is_remote=is_remote)
        remote_scope = classify_remote_scope(location, work_model=work_model, is_remote=is_remote)
        seniority = classify_seniority_title(title) or "unknown"

        employment_type = raw.get("employmentType") or None
        posted_at = parse_posted_at(raw.get("publishedAt"))

        compensation = raw.get("compensation") or {}
        comp_summary = compensation.get("compensationTierSummary") or ""
        salary = parse_salary(comp_summary)
        if comp_summary:
            salary["salary_raw"] = comp_summary

        job_url = raw.get("jobUrl") or None
        apply_url = raw.get("applyUrl") or None
        canonical_url = default_canonical_url(canonical=job_url, apply=apply_url)

        return DiscoveredJob(
            source=self.name,
            external_id=external_id,
            company=board,
            role=title,
            description=description,
            source_url=job_url,
            apply_url=apply_url,
            canonical_url=canonical_url,
            location_text=location or None,
            work_model=work_model,
            remote_scope=remote_scope,
            seniority=seniority,
            employment_type=employment_type,
            salary_min=salary["salary_min"],
            salary_max=salary["salary_max"],
            salary_currency=salary["salary_currency"],
            salary_period=salary["salary_period"],
            salary_raw=salary["salary_raw"],
            posted_at=posted_at,
            active_state="active",
            active_confidence="high",
            raw_payload=raw,
        )
