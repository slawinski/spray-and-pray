"""Cheap, deterministic eligibility prefilter.

Runs before any LLM call. Decides pass / fail / review for role family,
seniority, geography, and JD length. Framework fit is deliberately NOT a
prefilter concern — it belongs to Match Score v2.
"""

import re

from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.models import DiscoveredJob, PrefilterResult
from cv_optimizer.matching import MIN_JD_CHARS

# ── Geography knowledge ──────────────────────────────────────────────────────

WARSAW_TOKENS = ("warsaw", "warszawa", "warszaw")

_POLISH_CITIES = {
    "krakow", "kraków", "gdansk", "gdańsk", "wroclaw", "wrocław",
    "poznan", "poznań", "lodz", "łódź", "katowice", "gdynia", "szczecin",
    "lublin", "bialystok", "rzeszow", "torun",
}

_FOREIGN_CITIES = {
    "san francisco", "new york", "london", "berlin", "amsterdam", "paris",
    "toronto", "dublin", "munich", "hamburg", "barcelona", "madrid",
    "lisbon", "lisboa", "stockholm", "copenhagen", "oslo", "helsinki",
    "vienna", "zurich", "prague", "bratislava", "budapest", "bucharest",
    "sofia", "athens", "rome", "milan", "washington", "seattle", "austin",
    "boston", "chicago", "los angeles", "denver", "atlanta", "miami",
    "singapore", "dubai", "tel aviv", "kyiv", "minsk", "moscow",
    "bengaluru", "bangalore", "mumbai", "delhi", "sydney", "melbourne",
    "auckland", "tokyo", "seoul", "shanghai", "beijing", "hong kong",
}

_REMOTE_SCOPE_TOKENS = {
    "poland": ("poland",),
    "europe": ("europe", "european"),
    "eu": ("european union",),
    "eea": ("eea", "european economic area"),
    "emea": ("emea",),
    "worldwide": ("worldwide", "global", "anywhere"),
}

_COUNTRY_RESTRICTED = {
    "united states", "us only", "usa", "u.s.", "united kingdom", "uk only",
    "canada", "germany", "australia", "france", "spain", "italy",
    "netherlands", "sweden", "norway", "denmark", "finland", "austria",
    "switzerland", "ireland", "portugal", "czech", "india", "brazil",
    "japan", "south korea", "singapore", "israel", "ukraine", "romania",
}

_RESIDENCY_PATTERNS = (
    re.compile(r"must\s+(?:currently\s+)?reside\s+in", re.IGNORECASE),
    re.compile(r"must\s+be\s+located\s+in", re.IGNORECASE),
    re.compile(r"based\s+in\s+the\s+(us|usa|united states)", re.IGNORECASE),
)

_US_ONLY_PATTERN = re.compile(
    r"\b(us|usa|u\.s\.|united states)\s+only\b", re.IGNORECASE
)

# "Remote US", "US (Remote)", "(Remote US)", "Remote - India", "US only remote",
# etc. — aggregator titles often carry the real geography while location_text
# says "Anywhere". Adjacency to "remote" is required to avoid matching prose
# like "work with US clients".
_REMOTE_COUNTRY_TOKENS = (
    r"us|usa|u\.s\.|united states|uk|canada|germany|india|australia"
    r"|brazil|japan|singapore|france|spain|italy|netherlands|sweden"
    r"|norway|denmark|finland|austria|switzerland|ireland|portugal"
    r"|czech|israel|ukraine|romania"
)
_REMOTE_COUNTRY_TITLE_RE = re.compile(
    rf"\bremote\b[\s\-\(\):]*\b(?:{_REMOTE_COUNTRY_TOKENS})\b"
    rf"|\b(?:{_REMOTE_COUNTRY_TOKENS})\b[\s\-\(\):]*\bremote\b",
    re.IGNORECASE,
)

# A parenthetical that scopes the role to the US AND mentions remote —
# "(US-Based / Remote / Part-Time)", "(Remote: US)". This does NOT match
# "Remote worldwide (US-based startup)" because there the two words sit in
# different parentheticals / prose.
_PAREN_US_REMOTE_RE = re.compile(
    r"\([^()]*\b(?:us|usa|u\.s\.|united states)\b[^()]*\bremote\b[^()]*\)"
    r"|\([^()]*\bremote\b[^()]*\b(?:us|usa|u\.s\.|united states)\b[^()]*\)",
    re.IGNORECASE,
)

# ── Role family ──────────────────────────────────────────────────────────────

_ROLE_FAIL_PHRASES = (
    "backend",
    "data engineer",
    "data scientist",
    "data analyst",
    "machine learning engineer",
    "ml engineer",
    "devops",
    "site reliability",
    "sre",
    "platform engineer",
    "infrastructure engineer",
    "qa engineer",
    "quality assurance",
    "test engineer",
    "ios developer",
    "android developer",
    "mobile developer",
    "mobile engineer",
    "engineering manager",
    "product manager",
    "project manager",
    "ux designer",
    "ui designer",
    "product designer",
    "designer",
    "ux researcher",
    "developer advocate",
    "developer relations",
    "devrel",
    "sales engineer",
    "solutions architect",
    "support engineer",
    "security engineer",
    "embedded engineer",
    "firmware",
    "game developer",
    "blockchain",
    "sap consultant",
    "dba",
    "database administrator",
)

_ROLE_PASS_PHRASES = (
    "frontend",
    "front-end",
    "front end",
    "web engineer",
    "web developer",
    "ui engineer",
    "product engineer",
    "full stack",
    "fullstack",
    "full-stack",
    "typescript",
    "javascript",
    "react",
    "vue",
    "angular",
    "svelte",
    "next.js",
    "nextjs",
    "nuxt",
    "ember",
    "solidjs",
    "qwik",
)

_FRONTEND_HINTS = (
    "frontend", "front-end", "front end", "react", "vue", "angular",
    "svelte", "next.js", "nuxt", "javascript", "typescript", "css",
    "web application", "ui engineer", "browser",
)


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


# ── Prefilter API ────────────────────────────────────────────────────────────

def prefilter(
    job: DiscoveredJob,
    config: DiscoveryConfig,
) -> PrefilterResult:
    """Runs all cheap checks; the first hard failure wins."""
    jd_len = len(_norm(job.description))

    # 1. JD validity — cheapest, before anything else.
    if jd_len < MIN_JD_CHARS:
        return PrefilterResult(state="fail", reason="insufficient_description")

    # 2. Seniority.
    seniority = _classify_seniority(job)
    if seniority is not None:
        job.seniority = seniority
    sen_result = _check_seniority(job, config)
    if sen_result.state == "fail":
        return sen_result

    # 3. Role family.
    role_result = _check_role_family(job)
    if role_result.state == "fail":
        return role_result

    # 4. Geography.
    geo_result = _check_geography(job, config)
    if geo_result.state == "fail":
        return geo_result

    # Any remaining ambiguity → review (never reject ambiguity).
    if role_result.state == "review" or geo_result.state == "review":
        reason = []
        if role_result.state == "review":
            reason.append(role_result.reason)
        if geo_result.state == "review":
            reason.append(geo_result.reason)
        return PrefilterResult(state="review", reason="; ".join(reason))

    return PrefilterResult(state="pass", reason="eligible")


# ── Seniority ────────────────────────────────────────────────────────────────

_SENIORITY_TITLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("intern", re.compile(r"\bintern\b|\bstaż|\bstaz\b", re.IGNORECASE)),
    ("junior", re.compile(r"\bjunior\b|\bjunior\b|\bjr\.?\b", re.IGNORECASE)),
    ("senior", re.compile(r"\bsenior\b|\bsr\.?\b", re.IGNORECASE)),
    ("lead", re.compile(r"\blead\b", re.IGNORECASE)),
    ("principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
    ("staff", re.compile(r"\bstaff\b", re.IGNORECASE)),
    ("mid", re.compile(r"\bmid(?:-| )?level\b", re.IGNORECASE)),
]


def _classify_seniority(job: DiscoveredJob) -> str | None:
    title = _norm(job.role)
    for label, pattern in _SENIORITY_TITLE_PATTERNS:
        if pattern.search(title):
            return label
    return None


def _check_seniority(
    job: DiscoveredJob, config: DiscoveryConfig
) -> PrefilterResult:
    level = job.seniority
    if level in ("intern", "junior"):
        return PrefilterResult(state="fail", reason=f"seniority:{level}")
    if level == "staff" and not config.seniority.include_staff:
        return PrefilterResult(state="fail", reason="seniority:staff")
    if level == "lead" and not config.seniority.include_lead:
        return PrefilterResult(state="fail", reason="seniority:lead")
    if level == "principal" and not config.seniority.include_staff:
        return PrefilterResult(state="fail", reason="seniority:principal")
    if level in ("mid", "senior"):
        if level not in config.seniority.include:
            return PrefilterResult(state="fail", reason=f"seniority:{level}")
        return PrefilterResult(state="pass", reason=f"seniority:{level}")
    # Unlevelled: retained when config allows.
    if config.seniority.include_unleveled:
        return PrefilterResult(state="pass", reason="seniority:unleveled")
    return PrefilterResult(state="review", reason="seniority:unknown")


# ── Role family ──────────────────────────────────────────────────────────────

def _check_role_family(job: DiscoveredJob) -> PrefilterResult:
    title = _norm(job.role)

    # FAIL signals first: a framework word in the title never overrides an
    # explicit exclusion ("TypeScript Backend Engineer" is still backend).
    for phrase in _ROLE_FAIL_PHRASES:
        if phrase in title:
            return PrefilterResult(state="fail", reason=f"role:{phrase}")

    for phrase in _ROLE_PASS_PHRASES:
        if phrase in title:
            return PrefilterResult(state="pass", reason=f"role:{phrase}")

    # Generic titles ("Software Engineer") → inspect JD for frontend hints.
    description = _norm(job.description)
    hints = [h for h in _FRONTEND_HINTS if h in description]
    if len(hints) >= 2 or any(h in title for h in _FRONTEND_HINTS):
        return PrefilterResult(state="pass", reason="role:frontend-signal")
    if hints:
        return PrefilterResult(state="review", reason="role:ambiguous-frontend-signal")
    return PrefilterResult(state="review", reason="role:ambiguous")


# ── Geography ────────────────────────────────────────────────────────────────

def _check_geography(
    job: DiscoveredJob, config: DiscoveryConfig
) -> PrefilterResult:
    text = _norm(job.location_text)
    work_model = job.work_model
    scope = job.remote_scope

    # Country-restricted remote signals in the TITLE ("Remote US", "US
    # (Remote)", "Remote - India") — aggregators often leave location_text
    # as "Anywhere" while the title carries the real geography.
    combined = f"{text} {_norm(job.role)}"
    if _REMOTE_COUNTRY_TITLE_RE.search(combined):
        return PrefilterResult(
            state="fail", reason="geography:country-restricted-remote"
        )
    if _US_ONLY_PATTERN.search(combined):
        return PrefilterResult(state="fail", reason="geography:us-only")
    if _PAREN_US_REMOTE_RE.search(combined):
        return PrefilterResult(state="fail", reason="geography:us-remote")

    # Explicit residency constraints contradict Warsaw/Poland → fail.
    for pattern in _RESIDENCY_PATTERNS:
        if pattern.search(text):
            return PrefilterResult(state="fail", reason="geography:residency-constraint")

    is_remote = (
        work_model == "remote"
        or "remote" in text
        or scope not in ("unknown", "country_specific")
    )

    if "warsaw" in text or any(t in text for t in WARSAW_TOKENS):
        if not is_remote:
            if work_model == "onsite" and not config.locations.warsaw.onsite:
                return PrefilterResult(state="fail", reason="geography:warsaw-onsite-disabled")
            if work_model == "hybrid" and not config.locations.warsaw.hybrid:
                return PrefilterResult(state="fail", reason="geography:warsaw-hybrid-disabled")
            return PrefilterResult(state="pass", reason="geography:warsaw")
        # Warsaw mentioned but remote → falls through to remote handling.

    if is_remote:
        return _check_remote_geography(text, scope, config)

    # Onsite/hybrid elsewhere: explicit foreign city → fail; Polish city → fail
    # (only Warsaw onsite/hybrid is enabled); unknown city → review.
    for city in _FOREIGN_CITIES:
        if city in text:
            return PrefilterResult(state="fail", reason=f"geography:{city}")
    for city in _POLISH_CITIES:
        if city in text:
            return PrefilterResult(state="fail", reason=f"geography:{city}-onsite")

    if work_model == "unknown":
        return PrefilterResult(state="review", reason="geography:unknown")

    return PrefilterResult(state="review", reason="geography:ambiguous")


def _check_remote_geography(
    text: str, scope: str, config: DiscoveryConfig
) -> PrefilterResult:
    remote_cfg = config.locations.remote

    # "Work from anywhere in your region" has no precise eligibility
    # definition → ambiguous, do not reject.
    if "your region" in text or "their region" in text:
        return PrefilterResult(state="review", reason="geography:region-unspecified")

    # Explicit remote scope in structured field.
    if scope in ("poland", "europe", "eu", "eea", "emea", "worldwide"):
        flag = {
            "poland": remote_cfg.poland,
            "europe": remote_cfg.europe,
            "eu": remote_cfg.eu,
            "eea": remote_cfg.eea,
            "emea": remote_cfg.emea,
            "worldwide": remote_cfg.worldwide,
        }[scope]
        if flag:
            return PrefilterResult(state="pass", reason=f"geography:remote-{scope}")
        return PrefilterResult(state="review", reason=f"geography:remote-{scope}-disabled")

    # "Remote US only" / "US remote only" patterns.
    if _US_ONLY_PATTERN.search(text) or re.search(
        r"remote\s+(?:in\s+)?(?:the\s+)?(us|usa|u\.s\.|united states)\b", text
    ):
        return PrefilterResult(state="fail", reason="geography:us-only")
    if re.search(r"\bremote\s+(?:in\s+)?(?:the\s+)?uk\b", text):
        return PrefilterResult(state="fail", reason="geography:uk-only")

    # Explicit scope words in free text.
    for scope_name, tokens in _REMOTE_SCOPE_TOKENS.items():
        if any(t in text for t in tokens):
            flag = {
                "poland": remote_cfg.poland,
                "europe": remote_cfg.europe,
                "eu": remote_cfg.eu,
                "eea": remote_cfg.eea,
                "emea": remote_cfg.emea,
                "worldwide": remote_cfg.worldwide,
            }[scope_name]
            if flag:
                return PrefilterResult(state="pass", reason=f"geography:remote-{scope_name}")
            return PrefilterResult(state="review", reason=f"geography:remote-{scope_name}-disabled")

    # Country-restricted remote for a non-target country → fail.
    for country in _COUNTRY_RESTRICTED:
        if re.search(rf"\b{re.escape(country)}\b(?!\s*(?:based|company|team))", text):
            return PrefilterResult(state="fail", reason=f"geography:{country}-only")

    # Bare "remote" / "distributed" / "work from anywhere" → review.
    return PrefilterResult(state="review", reason="geography:remote-unspecified")
