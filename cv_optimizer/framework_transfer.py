"""Mainstream JavaScript frontend framework family.

Used by the Match Score (match-v2) to decide whether a named framework
requirement may be classified as ``framework_transfer`` /
``framework_depth_gap`` when the candidate lacks exact experience but has
substantial production experience with other mainstream JS frontend
frameworks.

Python owns this decision: the LLM proposes evidence levels, but only
technologies in this family may receive framework-transfer classifications.
This prevents the model from deciding that arbitrary technologies
(e.g. Django, Kubernetes, Terraform) are transferable merely because both
are programming tools.

English-word collisions are handled explicitly: names like "solid",
"next", "lit", "ember" appear in ordinary prose ("solid understanding",
"the next generation") and must only count when written in capitalized
proper-noun form or in an explicit ".js"-style alias.
"""

import re
from typing import Iterable

# ── Alias tables ─────────────────────────────────────────────────────────────
# _TOKEN_RE keeps dotted tokens intact, so "react.js" is ONE token.

# Unambiguous single-token aliases (dotted or suffixed forms included).
_SINGLE_ALIASES: dict[str, str] = {
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "next.js": "nextjs",
    "nextjs": "nextjs",
    "preact": "preact",
    "vue": "vue",
    "vue.js": "vue",
    "vuejs": "vue",
    "nuxt": "nuxt",
    "nuxt.js": "nuxt",
    "nuxtjs": "nuxt",
    "angular": "angular",
    "angular.js": "angular",
    "angularjs": "angular",
    "svelte": "svelte",
    "sveltekit": "sveltekit",
    "solidjs": "solid",
    "solid.js": "solid",
    "solidstart": "solidstart",
    "ember.js": "ember",
    "emberjs": "ember",
    "qwik": "qwik",
    "litelement": "lit",
}

# Multi-token window aliases.
_WINDOW_ALIASES: dict[str, str] = {
    "svelte kit": "sveltekit",
    "solid start": "solidstart",
    "lit element": "lit",
}

# Single-token names that collide with ordinary English words. Only accepted
# in capitalized proper-noun form in the original text.
_AMBIGUOUS_SINGLES: dict[str, str] = {
    "solid": "solid",
    "next": "nextjs",
    "ember": "ember",
    "lit": "lit",
}

_CAPITALIZED_AMBIGUOUS_RE = re.compile(r"\b(?:Solid|Ember|Lit|LIT)\b")

# Canonical names returned by normalization.
JS_FRONTEND_FRAMEWORKS: frozenset[str] = frozenset(
    {
        "react",
        "nextjs",
        "preact",
        "vue",
        "nuxt",
        "angular",
        "svelte",
        "sveltekit",
        "solid",
        "solidstart",
        "ember",
        "qwik",
        "lit",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _window_matches(tokens: list[str]) -> set[str]:
    found: set[str] = set()
    for length in (3, 2):
        for start in range(0, max(0, len(tokens) - length + 1)):
            candidate = " ".join(tokens[start : start + length])
            canonical = _WINDOW_ALIASES.get(candidate)
            if canonical:
                found.add(canonical)
    return found


def _single_matches(tokens: list[str], original: str) -> set[str]:
    found: set[str] = set()
    for token in tokens:
        canonical = _SINGLE_ALIASES.get(token)
        if canonical:
            found.add(canonical)
    if _CAPITALIZED_AMBIGUOUS_RE.search(original):
        for token in tokens:
            if token in _AMBIGUOUS_SINGLES:
                found.add(_AMBIGUOUS_SINGLES[token])
    return found


def normalize_framework_name(name: str) -> str | None:
    """Returns the canonical framework name, or None if not a family member.

    English-word collisions ("solid understanding", "the next generation",
    "lit by design") are rejected: ambiguous names must appear capitalized
    or in an explicit ".js"-style form.
    """
    tokens = _tokenize(name)
    if not tokens:
        return None
    window = _window_matches(tokens)
    if window:
        return sorted(window)[0]
    found = _single_matches(tokens, name)
    return sorted(found)[0] if found else None


def is_js_frontend_framework(name: str) -> bool:
    """True when `name` names a mainstream JS frontend framework."""
    return normalize_framework_name(name) is not None


def framework_names_in_text(text: str) -> set[str]:
    """All canonical framework names mentioned in a requirement/text."""
    tokens = _tokenize(text)
    return _window_matches(tokens) | _single_matches(tokens, text)


def extract_framework_requirement_name(requirement: str) -> str | None:
    """Extracts the framework named by a requirement string, if any.

    Used to validate LLM-proposed framework-transfer classifications:
    the requirement must actually name a mainstream JS frontend framework.
    """
    names = framework_names_in_text(requirement)
    if not names:
        return None
    return sorted(names)[0]


def candidate_frameworks(profile: dict) -> set[str]:
    """Frameworks evidenced anywhere in the match-profile projection.

    Scans skills and experience text; conservative (names only).
    """
    found: set[str] = set()

    def scan(value) -> None:
        if isinstance(value, str):
            found.update(framework_names_in_text(value))
        elif isinstance(value, dict):
            for v in value.values():
                scan(v)
        elif isinstance(value, list):
            for v in value:
                scan(v)

    scan(profile.get("skills", {}))
    scan(profile.get("experience", []))
    scan(profile.get("summary"))
    scan(profile.get("speaking_and_community", []))
    return found


def has_other_framework_evidence(profile: dict, target_framework: str) -> bool:
    """True when the profile evidences at least one mainstream JS frontend
    framework other than `target_framework`.

    Framework-transfer classifications are only credible when the candidate
    has substantial production experience with a *different* mainstream
    framework — never when the profile shows no framework experience at all.
    """
    return bool(candidate_frameworks(profile) - {normalize_framework_name(target_framework) or target_framework})


def validate_framework_transfer(
    requirement: str,
    evidence_level: str,
    profile: dict,
) -> tuple[str, str | None]:
    """Validates a framework-transfer classification proposed by the LLM.

    Returns (effective_evidence_level, warning).

    Rules:
    - Only ``framework_transfer`` / ``framework_depth_gap`` are checked.
    - The requirement must name a mainstream JS frontend framework.
    - The profile must evidence at least one other mainstream framework.
    - Otherwise the classification downgrades to ``none``.
    """
    if evidence_level not in ("framework_transfer", "framework_depth_gap"):
        return evidence_level, None

    target = extract_framework_requirement_name(requirement)
    if target is None:
        return "none", (
            f"framework-transfer classification rejected for "
            f"'{requirement}': not a mainstream JS frontend framework"
        )
    if not has_other_framework_evidence(profile, target):
        return "none", (
            f"framework-transfer classification rejected for "
            f"'{requirement}': no other mainstream JS frontend framework "
            "evidence in candidate profile"
        )
    return evidence_level, None


def framework_aliases_normalized(names: Iterable[str]) -> set[str]:
    """Normalizes an iterable of framework names to canonical members."""
    return {
        canonical
        for name in names
        if (canonical := normalize_framework_name(name)) is not None
    }
