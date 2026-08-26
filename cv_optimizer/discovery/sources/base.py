"""Source adapter contract and shared normalization utilities.

Every provider adapter implements the same ``JobSource`` contract and
returns provider-neutral ``DiscoveredJob`` models. Provider-specific
response shapes must never leak into the domain layer.
"""

import html as html_lib
import logging
import re
from abc import ABC, abstractmethod
from typing import Protocol

import requests

from cv_optimizer.discovery.models import DiscoveredJob, DiscoveryQuery

logger = logging.getLogger(__name__)


class SourceError(Exception):
    """A provider failed for this run; other providers continue."""


class RateLimited(SourceError):
    """HTTP 429 or provider rate limiting — stop this provider for the run."""


class JobSource(Protocol):
    name: str

    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]: ...


class HttpJobSource(ABC):
    """Shared HTTP behavior: timeout, rate-limit detection, error isolation."""

    name: str = "base"
    timeout: float = 30.0

    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._session = requests.Session()

    def _get_json(self, url: str, *, params: dict | None = None) -> dict | list:
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SourceError(f"{self.name}: request failed: {exc}") from exc
        if response.status_code == 429:
            raise RateLimited(f"{self.name}: rate limited (HTTP 429)")
        if response.status_code >= 400:
            raise SourceError(
                f"{self.name}: HTTP {response.status_code} from {url}"
            )
        return response.json()

    @abstractmethod
    def fetch(self, query: DiscoveryQuery) -> list[DiscoveredJob]: ...


# ── Shared classification helpers ────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&(?:amp|nbsp|quot|#39|lt|gt|#\d+);")


def strip_html(text: str) -> str:
    """Removes HTML tags and decodes entities into plain text."""
    text = _HTML_TAG_RE.sub(" ", text or "")
    text = html_lib.unescape(text)
    text = _ENTITY_RE.sub(" ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def clean_text(text: str) -> str:
    """Collapses whitespace and normalizes weird spacing."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_salary(raw: str | None) -> dict:
    """Best-effort parse of a compensation string into numeric bounds.

    Returns {'salary_min', 'salary_max', 'salary_currency', 'salary_period',
    'salary_raw'}. Values are None when unparseable; the raw string is kept.
    """
    result = {
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
        "salary_raw": raw,
    }
    if not raw:
        return result

    text = raw.strip()
    currency_match = re.search(r"([$€£]|\b(?:USD|EUR|GBP|PLN)\b)", text)
    if currency_match:
        symbol = currency_match.group(1)
        result["salary_currency"] = {
            "$": "USD", "€": "EUR", "£": "GBP",
        }.get(symbol, symbol.upper())

    if re.search(r"\b(?:year|annual|annually|yr)\b", text, re.IGNORECASE):
        result["salary_period"] = "year"
    elif re.search(r"\b(?:month|monthly)\b", text, re.IGNORECASE):
        result["salary_period"] = "month"
    elif re.search(r"\b(?:hour|hourly)\b", text, re.IGNORECASE):
        result["salary_period"] = "hour"

    numbers = []
    for value, multiplier in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?", text):
        num = float(value.replace(",", ""))
        if multiplier:
            num *= 1000
        numbers.append(num)
    numbers = sorted(set(numbers))
    if numbers:
        result["salary_min"] = min(numbers)
        result["salary_max"] = max(numbers) if len(numbers) > 1 else None
    return result


WORK_MODEL_HINTS = {
    "remote": ("remote", "work from home", "wfh", "anywhere"),
    "hybrid": ("hybrid",),
    "onsite": ("on-site", "onsite", "on site", "office"),
}


def classify_work_model(
    location_text: str | None,
    workplace_type: str | None = None,
    is_remote: bool | None = None,
) -> str:
    """Returns 'remote' | 'hybrid' | 'onsite' | 'unknown'."""
    if workplace_type:
        wt = workplace_type.lower()
        if "remote" in wt:
            return "remote"
        if "hybrid" in wt:
            return "hybrid"
        if "on" in wt and "site" in wt:
            return "onsite"
    if is_remote is True:
        return "remote"
    text = clean_text(location_text).lower()
    for model, hints in WORK_MODEL_HINTS.items():
        if any(h in text for h in hints):
            return model
    return "unknown"


REMOTE_SCOPE_HINTS = {
    "worldwide": ("worldwide", "global", "anywhere", "work from anywhere"),
    "emea": ("emea",),
    "europe": ("europe", "european union", "eu", "eea"),
    "poland": ("poland",),
}


def classify_remote_scope(
    location_text: str | None,
    work_model: str | None = None,
    is_remote: bool | None = None,
) -> str:
    """Returns a remote_scope Literal for remote roles."""
    text = clean_text(location_text).lower()
    for scope, hints in REMOTE_SCOPE_HINTS.items():
        if any(h in text for h in hints):
            return scope
    if (work_model == "remote" or is_remote) and text:
        return "unknown"
    return "unknown"


SENIORITY_TITLE_RE = [
    ("intern", re.compile(r"\bintern\b|\bstaż\b|\bstaz\b", re.IGNORECASE)),
    ("junior", re.compile(r"\bjunior\b|\bjr\.?\b", re.IGNORECASE)),
    ("lead", re.compile(r"\blead\b", re.IGNORECASE)),
    ("principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
    ("staff", re.compile(r"\bstaff\b", re.IGNORECASE)),
    ("senior", re.compile(r"\bsenior\b|\bsr\.?\b", re.IGNORECASE)),
    ("mid", re.compile(r"\bmid(?:-| )?level\b", re.IGNORECASE)),
]


def classify_seniority_title(title: str | None) -> str | None:
    if not title:
        return None
    for label, pattern in SENIORITY_TITLE_RE:
        if pattern.search(title):
            return label
    return None


def parse_posted_at(value: object) -> "datetime | None":  # noqa: F821
    """Parses ISO timestamps and rough 'N days ago' strings."""
    from datetime import datetime, timedelta, timezone

    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass
    m = re.match(r"(\d+)\s*(day|week|month|hour)s?\s+ago", text, re.IGNORECASE)
    if m:
        count = int(m.group(1))
        unit = m.group(2).lower()
        delta = {
            "hour": timedelta(hours=count),
            "day": timedelta(days=count),
            "week": timedelta(weeks=count),
            "month": timedelta(days=30 * count),
        }[unit]
        return datetime.now(timezone.utc) - delta
    return None


def default_canonical_url(
    *, canonical: str | None = None, apply: str | None = None, source: str | None = None
) -> str | None:
    from cv_optimizer.discovery.dedupe import normalize_url

    for candidate in (canonical, apply, source):
        normalized = normalize_url(candidate)
        if normalized:
            return normalized
    return None
