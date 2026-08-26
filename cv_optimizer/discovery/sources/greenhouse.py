"""Greenhouse public board API adapter.

GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs
GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}   (full JD)

Only public postings are returned. Board identifiers are configured
explicitly; per-job detail fetches are bounded by max_jobs_per_board.
"""

import logging

from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.models import DiscoveredJob, DiscoveryQuery
from cv_optimizer.discovery.sources.base import (
    HttpJobSource,
    RateLimited,
    SourceError,
    classify_remote_scope,
    classify_seniority_title,
    classify_work_model,
    clean_text,
    default_canonical_url,
    parse_posted_at,
    strip_html,
)

logger = logging.getLogger(__name__)

BOARDS_ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
JOB_ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"

MAX_JOBS_PER_BOARD = 200


class GreenhouseSource(HttpJobSource):
    name = "greenhouse"

    def __init__(
        self,
        boards: list[str],
        *,
        timeout: float = 30.0,
        max_jobs_per_board: int = MAX_JOBS_PER_BOARD,
    ) -> None:
        super().__init__(timeout=timeout)
        self.boards = [b.strip().rstrip("/") for b in boards if b and b.strip()]
        self.max_jobs_per_board = max_jobs_per_board

    @classmethod
    def from_config(cls, config: DiscoveryConfig) -> "GreenhouseSource":
        cfg = config.boards_for("greenhouse")
        return cls(boards=cfg.boards or cfg.sites)

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]:
        if not self.boards:
            logger.info("greenhouse: no boards configured; skipping")
            return []
        jobs: list[DiscoveredJob] = []
        for board in self.boards:
            url = BOARDS_ENDPOINT.format(board=board)
            data = self._get_json(url)
            if not isinstance(data, dict):
                raise SourceError(f"greenhouse: unexpected response shape for {board}")
            board_jobs = (data.get("jobs") or [])[: self.max_jobs_per_board]
            for raw in board_jobs:
                detail = self._fetch_detail(board, raw.get("id"))
                job = self.normalize_job(detail or raw, board=board)
                if job is not None:
                    jobs.append(job)
        return jobs

    def _fetch_detail(self, board: str, job_id) -> dict | None:
        if job_id is None:
            return None
        try:
            data = self._get_json(JOB_ENDPOINT.format(board=board, job_id=job_id))
        except RateLimited:
            raise  # stop requesting this provider for the run — no busy-loop
        except SourceError:
            logger.warning("greenhouse: could not fetch detail for job %s", job_id)
            return None
        return data if isinstance(data, dict) else None

    def normalize_job(self, raw: dict, *, board: str) -> DiscoveredJob | None:
        title = clean_text(raw.get("title") or "")
        if not title:
            return None
        external_id = str(raw.get("id") or "")
        if not external_id:
            return None

        content = raw.get("content") or ""
        description = strip_html(str(content)) if content else ""

        location_info = raw.get("location") or {}
        location = (
            clean_text(location_info.get("name") or "")
            if isinstance(location_info, dict)
            else clean_text(str(location_info))
        )

        work_model = classify_work_model(location)
        remote_scope = classify_remote_scope(location, work_model=work_model)
        seniority = classify_seniority_title(title) or "unknown"

        absolute_url = raw.get("absolute_url") or None
        canonical_url = default_canonical_url(canonical=absolute_url)

        posted_at = parse_posted_at(raw.get("updated_at") or raw.get("first_published"))

        return DiscoveredJob(
            source=self.name,
            external_id=external_id,
            company=board,
            role=title,
            description=description,
            source_url=absolute_url,
            apply_url=absolute_url,
            canonical_url=canonical_url,
            location_text=location or None,
            work_model=work_model,
            remote_scope=remote_scope,
            seniority=seniority,
            posted_at=posted_at,
            active_state="active",
            active_confidence="high",
            raw_payload=raw,
        )
