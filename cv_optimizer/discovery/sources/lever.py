"""Lever public postings API adapter.

GET https://api.lever.co/v0/postings/{site}?mode=json

Published postings are publicly visible. Each configured `site` is the
company's Lever board slug.
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
)

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.lever.co/v0/postings/{site}"


class LeverSource(HttpJobSource):
    name = "lever"

    def __init__(self, sites: list[str], *, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.sites = [s.strip().rstrip("/") for s in sites if s and s.strip()]

    @classmethod
    def from_config(cls, config: DiscoveryConfig) -> "LeverSource":
        boards = config.boards_for("lever")
        return cls(sites=boards.sites or boards.boards)

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]:
        if not self.sites:
            logger.info("lever: no sites configured; skipping")
            return []
        jobs: list[DiscoveredJob] = []
        for site in self.sites:
            url = ENDPOINT.format(site=site)
            data = self._get_json(url, params={"mode": "json"})
            if not isinstance(data, list):
                raise SourceError(f"lever: unexpected response shape for {site}")
            for raw in data:
                job = self.normalize_job(raw, site=site)
                if job is not None:
                    jobs.append(job)
        return jobs

    def normalize_job(self, raw: dict, *, site: str) -> DiscoveredJob | None:
        title = clean_text(raw.get("text") or "")
        if not title:
            return None
        external_id = str(raw.get("id") or "")
        if not external_id:
            return None

        description = clean_text(raw.get("descriptionPlain") or raw.get("description") or "")

        categories = raw.get("categories") or {}
        location = clean_text(categories.get("location") or "")
        commitment = clean_text(categories.get("commitment") or "") or None

        workplace_type = raw.get("workplaceType") or None
        work_model = classify_work_model(location, workplace_type=workplace_type)
        remote_scope = classify_remote_scope(location, work_model=work_model)
        seniority = classify_seniority_title(title) or "unknown"

        hosted_url = raw.get("hostedUrl") or None
        apply_url = raw.get("applyUrl") or None
        canonical_url = default_canonical_url(canonical=hosted_url, apply=apply_url)

        posted_at = parse_posted_at(raw.get("createdAt"))

        return DiscoveredJob(
            source=self.name,
            external_id=external_id,
            company=site,
            role=title,
            description=description,
            source_url=hosted_url,
            apply_url=apply_url,
            canonical_url=canonical_url,
            location_text=location or None,
            work_model=work_model,
            remote_scope=remote_scope,
            seniority=seniority,
            employment_type=commitment,
            posted_at=posted_at,
            active_state="active",
            active_confidence="high",
            raw_payload=raw,
        )
