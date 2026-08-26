"""Google Jobs via SerpApi — the broad market discovery source."""

import logging
import os
from typing import Any

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
    strip_html,
)

logger = logging.getLogger(__name__)

ENDPOINT = "https://serpapi.com/search"
DEFAULT_MAX_PAGES = 2

# Hosts that are aggregator/redirect links, never the real job page.
_TRACKING_HOSTS = {
    "google.com", "www.google.com", "google.co.uk", "www.google.co.uk",
    "serpapi.com", "www.serpapi.com",
}


def _is_tracking_url(url: str) -> bool:
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url).hostname or "").lower() in _TRACKING_HOSTS
    except ValueError:
        return False


class SerpApiSource(HttpJobSource):
    """Fetches Google Jobs results through SerpApi.

    Key handling: the API key is read from the SERPAPI_API_KEY environment
    variable and never logged or persisted.
    """

    name = "serpapi"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        max_pages_per_query: int = DEFAULT_MAX_PAGES,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.max_pages_per_query = max_pages_per_query

    def _require_key(self) -> None:
        if not self.api_key:
            raise SourceError(
                "serpapi: SERPAPI_API_KEY is not set; skipping source"
            )

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]:
        self._require_key()
        jobs: list[DiscoveredJob] = []
        params: dict[str, Any] = {
            "engine": "google_jobs",
            "q": query.q,
            "hl": "en",
            "api_key": self.api_key,
        }
        if query.location:
            params["location"] = query.location

        pages_fetched = 0
        while pages_fetched < self.max_pages_per_query:
            data = self._get_json(ENDPOINT, params=params)
            if not isinstance(data, dict):
                raise SourceError("serpapi: unexpected response shape")
            page_jobs = self.normalize_page(data)
            jobs.extend(page_jobs)
            pages_fetched += 1

            pagination = data.get("serpapi_pagination") or {}
            next_token = pagination.get("next_page_token")
            if not next_token:
                break
            params = {**params, "next_page_token": next_token}

        return jobs

    # ── Normalization ────────────────────────────────────────────────────────

    def normalize_page(self, data: dict) -> list[DiscoveredJob]:
        results = data.get("jobs_results") or []
        jobs = []
        for raw in results:
            job = self.normalize_job(raw)
            if job is not None:
                jobs.append(job)
        return jobs

    def normalize_job(self, raw: dict) -> DiscoveredJob | None:
        title = clean_text(raw.get("title") or "")
        company = clean_text(raw.get("company_name") or raw.get("via") or "")
        external_id = str(raw.get("job_id") or "").strip()

        if not title or not company:
            return None
        if not external_id:
            # Google job_id is the stable identity; without it the result is
            # unusable for dedupe.
            external_id = raw.get("share_link") or raw.get("apply_link") or ""
            if not external_id:
                return None
            external_id = str(external_id)

        description = self._extract_description(raw)
        location = clean_text(raw.get("location") or "")
        extensions = raw.get("detected_extensions") or {}
        posted_at = parse_posted_at(extensions.get("posted_at"))

        share_link = raw.get("share_link") or None
        best_url = self._best_job_url(raw)
        canonical_url = default_canonical_url(canonical=best_url, apply=share_link)

        workplace_type = extensions.get("schedule_type")
        work_model = classify_work_model(location, workplace_type=workplace_type)
        remote_scope = classify_remote_scope(location, work_model=work_model)
        seniority = classify_seniority_title(title) or "unknown"

        salary = parse_salary(extensions.get("salary"))
        salary["salary_raw"] = extensions.get("salary") or salary["salary_raw"]

        raw_payload = dict(raw)
        raw_payload.pop("thumbnail", None)  # drop binary junk if any

        return DiscoveredJob(
            source=self.name,
            external_id=external_id,
            company=company,
            role=title,
            description=description,
            source_url=share_link,
            apply_url=best_url,
            canonical_url=canonical_url,
            location_text=location or None,
            work_model=work_model,
            remote_scope=remote_scope,
            seniority=seniority,
            employment_type=workplace_type,
            salary_min=salary["salary_min"],
            salary_max=salary["salary_max"],
            salary_currency=salary["salary_currency"],
            salary_period=salary["salary_period"],
            salary_raw=salary["salary_raw"],
            posted_at=posted_at,
            active_state="unknown",
            active_confidence="medium",
            raw_payload=raw_payload,
        )

    @staticmethod
    def _best_job_url(raw: dict) -> str | None:
        """The most useful real-world URL for a result.

        Google Jobs responses bury the actual job page in apply_options /
        source_link while apply_link/share_link are frequently google.com
        redirect URLs. Prefer the first real URL; fall back to redirects
        only when nothing real exists (they at least carry the job identity).
        """
        candidates: list[str] = []
        for value in (raw.get("apply_link"),):
            if value and not _is_tracking_url(str(value)):
                candidates.append(str(value))
        for option in raw.get("apply_options") or []:
            link = option.get("link") if isinstance(option, dict) else None
            if link and not _is_tracking_url(str(link)):
                candidates.append(str(link))
        for value in (raw.get("source_link"),):
            if value and not _is_tracking_url(str(value)):
                candidates.append(str(value))
        if candidates:
            return candidates[0]
        # Redirect fallbacks: apply_link first, then the google share link.
        for value in (raw.get("apply_link"), raw.get("share_link")):
            if value:
                return str(value)
        return None

    @staticmethod
    def _extract_description(raw: dict) -> str:
        description = raw.get("description") or ""
        description = strip_html(str(description))
        if clean_text(description):
            return clean_text(description)

        # Fall back to job highlights (title + items).
        highlights = raw.get("job_highlights") or []
        parts = []
        for highlight in highlights:
            if not isinstance(highlight, dict):
                continue
            heading = clean_text(highlight.get("title") or "")
            items = [
                clean_text(item) for item in (highlight.get("items") or [])
            ]
            items = [i for i in items if i]
            if heading:
                parts.append(f"{heading}: " + "; ".join(items))
            elif items:
                parts.extend(items)
        return "\n".join(parts)
