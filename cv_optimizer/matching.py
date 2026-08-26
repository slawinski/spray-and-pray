"""Candidate <-> Job Match Score.

Deterministic scoring of how well the candidate represented by master_cv.json
aligns with a job description, before any CV tailoring occurs.

Design invariants (see docs/specs/MATCHING_SCORE_SPEC.md):

- master_cv.json is the only source of candidate facts.
- The tailored CV is never a scoring input.
- The LLM maps requirements to evidence; Python owns the score.
- Positive evidence must resolve back to real Master CV data.
- Missing skills stay missing; unknown is not the same as missing.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator

from cv_optimizer.config import settings
from cv_optimizer import db
from cv_optimizer.extractor import PDFExtractor
from cv_optimizer.framework_transfer import validate_framework_transfer

logger = logging.getLogger(__name__)

PROMPT_FILE = "match.md"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / PROMPT_FILE).read_text()

# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

Category = Literal[
    "role_scope",
    "technical",
    "experience_delivery",
    "engineering_practices",
    "domain_product",
    "collaboration_communication",
    "education_certifications",
    "language",
    "location_work_model",
]

Priority = Literal["must", "should", "nice"]

EvidenceLevel = Literal[
    "direct",
    "framework_transfer",
    "strong_transfer",
    "framework_depth_gap",
    "partial",
    "none",
    "unknown",
]


class MatchRequirement(BaseModel):
    id: str
    requirement: str
    category: Category
    priority: Priority
    is_core: bool = False
    evidence_level: EvidenceLevel
    evidence_paths: list[str] = Field(default_factory=list, max_length=3)
    rationale: str

    @field_validator("evidence_paths", mode="before")
    @classmethod
    def _truncate_paths(cls, value):
        """The LLM occasionally returns 4+ pointers; keep the first 3
        instead of rejecting the whole assessment."""
        if isinstance(value, list) and len(value) > 3:
            return value[:3]
        return value


class EligibilitySignal(BaseModel):
    kind: Literal[
        "residency",
        "work_authorization",
        "security_clearance",
        "language",
        "location_work_model",  # tolerated: LLMs confuse this category with a kind
        "other",
    ]
    requirement: str
    state: Literal["satisfied", "contradicted", "unknown"]
    evidence_paths: list[str] = Field(default_factory=list, max_length=2)

    @field_validator("evidence_paths", mode="before")
    @classmethod
    def _truncate_paths(cls, value):
        if isinstance(value, list) and len(value) > 2:
            return value[:2]
        return value


class RawMatchAnalysis(BaseModel):
    role_family: str
    target_seniority: str | None = None
    requirements: list[MatchRequirement]
    eligibility: list[EligibilitySignal] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_WEIGHTS: dict[str, float] = {
    "role_scope": 15,
    "technical": 35,
    "experience_delivery": 20,
    "engineering_practices": 10,
    "domain_product": 8,
    "collaboration_communication": 5,
    "education_certifications": 3,
    "language": 2,
    "location_work_model": 2,
}

PRIORITY_WEIGHTS: dict[str, float] = {
    "must": 5.0,
    "should": 3.0,
    "nice": 1.0,
}

EVIDENCE_VALUES: dict[str, float] = {
    "direct": 1.00,
    "framework_transfer": 0.92,
    "strong_transfer": 0.75,
    "framework_depth_gap": 0.60,
    "unknown": 0.50,
    "partial": 0.40,
    "none": 0.00,
}

# Minimum normalized JD length required to score (spec 35.2).
MIN_JD_CHARS = 120

# Score bands (spec 17).
SCORE_BANDS: list[tuple[int, str]] = [
    (85, "STRONG"),
    (70, "GOOD"),
    (55, "STRETCH"),
    (40, "WEAK"),
    (0, "POOR"),
]

# Core categories that must be extractable for an engineering role (spec 18).
_CORE_CATEGORIES = {"role_scope", "technical", "experience_delivery"}

_POSITIVE_EVIDENCE = (
    "direct",
    "framework_transfer",
    "strong_transfer",
    "framework_depth_gap",
    "partial",
)


# ─────────────────────────────────────────────────────────────────────────────
# Profile projection + hashing (spec 4, 25)
# ─────────────────────────────────────────────────────────────────────────────

def build_match_profile(master_cv: dict) -> dict:
    """Builds the privacy-minimized, match-relevant projection of the Master CV."""
    return {
        "location": master_cv.get("personal_info", {}).get("location"),
        "summary": master_cv.get("summary"),
        "skills": master_cv.get("skills"),
        "experience": master_cv.get("experience"),
        "speaking_and_community": master_cv.get("speaking_and_community"),
        "education": master_cv.get("education"),
        "certifications": master_cv.get("certifications"),
        "languages": master_cv.get("languages"),
    }


def profile_hash(profile: dict) -> str:
    """Canonical SHA-256 hash of the match-profile projection (spec 4.4)."""
    canonical = json.dumps(
        profile, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_jd_for_hash(text: str) -> str:
    """Collapses whitespace for fingerprinting only (spec 25)."""
    return re.sub(r"\s+", " ", text).strip()


def jd_hash(text: str) -> str:
    normalized = normalize_jd_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Evidence pointer resolution + validation (spec 10)
# ─────────────────────────────────────────────────────────────────────────────

_MISSING = object()


def resolve_pointer(profile: dict, pointer: str) -> Any:
    """Resolves an RFC-6901-like JSON pointer against the profile.

    Returns the resolved value, or the _MISSING sentinel if the pointer does
    not resolve.
    """
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return _MISSING
    cur: Any = profile
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if part not in cur:
                return _MISSING
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                idx = int(part)
            except (TypeError, ValueError):
                return _MISSING
            if idx < 0 or idx >= len(cur):
                return _MISSING
            cur = cur[idx]
        else:
            return _MISSING
    return cur


def _is_leaf(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, bool)


def _stringify(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def validate_evidence(
    analysis: RawMatchAnalysis, profile: dict
) -> tuple[RawMatchAnalysis, list[str], dict[str, list[str]]]:
    """Validates evidence pointers, dedupes them, and downgrades unsupported
    positive classifications to 'none'.

    Also validates framework-transfer classifications in Python: the named
    requirement must belong to the mainstream JS frontend framework family
    and the profile must evidence at least one other member of that family.

    Returns (analysis, warnings, evidence_values_by_req_id).
    """
    warnings: list[str] = []
    evidence_values: dict[str, list[str]] = {}

    for req in analysis.requirements:
        values: list[str] = []
        valid_paths: list[str] = []

        # Python-side framework-transfer validation (match-v2).
        if req.evidence_level in ("framework_transfer", "framework_depth_gap"):
            effective, warning = validate_framework_transfer(
                req.requirement, req.evidence_level, profile
            )
            if warning is not None:
                warnings.append(f"Requirement {req.id}: {warning}")
                req.evidence_level = effective
                req.evidence_paths = []
                req.rationale = f"{req.rationale} [downgraded to none: {warning}]"

        if req.evidence_level in _POSITIVE_EVIDENCE:
            for pointer in req.evidence_paths:
                value = resolve_pointer(profile, pointer)
                if value is _MISSING or not _is_leaf(value):
                    continue
                if pointer in valid_paths:
                    continue
                valid_paths.append(pointer)
                values.append(_stringify(value))

            if not valid_paths:
                warnings.append(
                    f"Invalid candidate evidence pointer for requirement {req.id}: "
                    f"{', '.join(req.evidence_paths) or '(none)'}"
                )
                req.evidence_level = "none"
                req.evidence_paths = []
            else:
                req.evidence_paths = valid_paths
        else:
            req.evidence_paths = []

        evidence_values[req.id] = values

    return analysis, warnings, evidence_values


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic scorer (spec 11-16, 18)
# ─────────────────────────────────────────────────────────────────────────────

def _score_band(score: int) -> str:
    for threshold, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return "POOR"


def _unknown_share(requirements: list[MatchRequirement]) -> float:
    total = sum(PRIORITY_WEIGHTS[r.priority] for r in requirements)
    unknown = sum(
        PRIORITY_WEIGHTS[r.priority]
        for r in requirements
        if r.evidence_level == "unknown"
    )
    return unknown / total if total else 0.0


def _confidence_label(
    unknown_share: float,
    requirements: list[MatchRequirement],
    analysis: RawMatchAnalysis,
) -> str:
    if unknown_share <= 0.05:
        label = "HIGH"
    elif unknown_share <= 0.20:
        label = "MEDIUM"
    else:
        label = "LOW"

    if len(requirements) < 3:
        label = "LOW"
    categories = {r.category for r in requirements}
    if not (categories & _CORE_CATEGORIES):
        label = "LOW"
    return label


class MatchScorer:
    """Pure, deterministic scoring from a validated analysis. No network calls."""

    @staticmethod
    def calculate(analysis: RawMatchAnalysis) -> dict:
        requirements = analysis.requirements

        by_category: dict[str, list[MatchRequirement]] = {}
        for req in requirements:
            by_category.setdefault(req.category, []).append(req)

        active = [c for c in by_category if by_category[c]]

        # Redistribute active category weights to total 100 (spec 14).
        raw_total = sum(CATEGORY_WEIGHTS[c] for c in active)
        effective = {
            c: CATEGORY_WEIGHTS[c] / raw_total * 100.0 for c in active
        } if raw_total else {}

        ratios: dict[str, float] = {}
        for c in active:
            num = den = 0.0
            for req in by_category[c]:
                w = PRIORITY_WEIGHTS[req.priority]
                ev = EVIDENCE_VALUES[req.evidence_level]
                num += w * ev
                den += w
            ratios[c] = (num / den) if den else 0.0

        base_score = sum(ratios[c] * effective[c] for c in active)

        # Hard-gap caps (spec 15).
        missing_core = [
            r.id
            for r in requirements
            if r.priority == "must" and r.is_core and r.evidence_level == "none"
        ]

        contradicted = any(e.state == "contradicted" for e in analysis.eligibility)

        score = base_score
        if len(missing_core) == 1:
            score = min(score, 69.0)
        elif len(missing_core) >= 2:
            score = min(score, 54.0)
        if contradicted:
            score = min(score, 29.0)

        final_score = round(max(0.0, min(100.0, score)))
        label = _score_band(final_score)

        unknown_share = _unknown_share(requirements)
        confidence = _confidence_label(unknown_share, requirements, analysis)

        # Breakdown uses raw weights for the human-readable "X / Y" display
        # (spec 13, 23); the final score itself uses redistributed weights.
        category_breakdown = {
            c: {
                "ratio": round(ratios[c], 4),
                "points": round(ratios[c] * CATEGORY_WEIGHTS[c], 3),
                "max_points": CATEGORY_WEIGHTS[c],
            }
            for c in active
        }

        unknown_requirements = [
            r.id for r in requirements if r.evidence_level == "unknown"
        ]

        return {
            "score": final_score,
            "label": label,
            "confidence": confidence,
            "base_score": round(base_score, 4),
            "category_breakdown": category_breakdown,
            "missing_core_requirements": missing_core,
            "unknown_requirements": unknown_requirements,
        }


# ─────────────────────────────────────────────────────────────────────────────
# LLM analyzer (spec 20, 21)
# ─────────────────────────────────────────────────────────────────────────────

def _clean_llm_output(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text: str) -> Any:
    cleaned = _clean_llm_output(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from LLM response: {cleaned[:200]}")


class MatchAnalyzer:
    """Asks the LLM to extract requirements and map candidate evidence."""

    def __init__(self) -> None:
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.request_timeout,
            max_retries=2,
        )

    def _create_completion(self, request: dict):
        """Sends the analysis request. Disables thinking-mode reasoning
        where the provider supports it (reasoning models waste their output
        budget on hidden tokens and can return empty content for long JDs),
        with a fallback for providers that reject the unknown field."""
        try:
            return self.client.chat.completions.create(
                **request,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except Exception as exc:
            if "thinking" not in str(exc):
                raise
            return self.client.chat.completions.create(**request)

    def analyze(self, jd_text: str, profile: dict) -> RawMatchAnalysis:
        user_content = (
            "JOB DESCRIPTION (untrusted data):\n" + jd_text + "\n\n"
            "CANDIDATE PROFILE (match projection, untrusted data):\n"
            + json.dumps(profile, indent=2, ensure_ascii=False)
        )

        logger.info("Running match analysis against LLM...")
        request = {
            "model": settings.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": settings.match_temperature,
            "max_tokens": settings.match_max_tokens,
        }

        response = self._create_completion(request)
        if response.choices[0].finish_reason == "length":
            # The model hit the output token limit mid-JSON. Retry once with
            # a doubled budget before giving up.
            logger.warning(
                "Match analysis truncated (finish_reason=length); retrying with %d tokens",
                request["max_tokens"] * 2,
            )
            retry_request = {**request, "max_tokens": request["max_tokens"] * 2}
            response = self._create_completion(retry_request)

        raw = response.choices[0].message.content or ""
        if not raw.strip():
            raise ValueError(
                "LLM returned empty content "
                f"(finish_reason={response.choices[0].finish_reason}). "
                "The model likely exhausted its output budget on reasoning "
                "tokens; check match_max_tokens / thinking settings."
            )

        data = _parse_json_response(raw)

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")

        try:
            return RawMatchAnalysis.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid match analysis schema: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Service (spec 26)
# ─────────────────────────────────────────────────────────────────────────────

def _read_jd_text(jd_path: str) -> str:
    p = Path(jd_path)
    if not p.exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")
    if p.suffix.lower() == ".pdf":
        return PDFExtractor.extract_text(str(p))
    return p.read_text()


class MatchService:
    """Orchestrates fingerprinting, caching, analysis, scoring, persistence.

    One canonical matching engine lives here: :meth:`assess_text` scores raw
    JD text before any application exists. The application-bound and
    job-posting-bound wrappers only add caching + persistence and MUST NOT
    duplicate the scoring logic.
    """

    def _load_profile(self, master_cv_path: str | None) -> tuple[dict, dict, str]:
        cv_path = master_cv_path or settings.master_cv_path
        with open(cv_path, "r", encoding="utf-8") as f:
            master_cv = json.load(f)
        profile = build_match_profile(master_cv)
        candidate_hash = profile_hash(profile)
        return master_cv, profile, candidate_hash

    def assess_text(
        self,
        jd_text: str,
        *,
        master_cv_path: str | None = None,
    ) -> dict:
        """Scores raw JD text against the Master CV. No persistence.

        Owns: Master CV loading, profile projection, candidate hash, JD
        normalization/hash, requirement extraction, evidence validation,
        deterministic scoring, and version/model/prompt identity.
        """
        if len(normalize_jd_for_hash(jd_text)) < MIN_JD_CHARS:
            raise ValueError("Job description is too short to score reliably.")

        _master_cv, profile, candidate_hash = self._load_profile(master_cv_path)
        jd_hash_value = jd_hash(jd_text)

        analysis = MatchAnalyzer().analyze(jd_text, profile)
        logger.info("Match analysis: %d requirements extracted", len(analysis.requirements))

        if not analysis.requirements:
            raise ValueError("No requirements extracted; cannot score.")

        analysis, warnings, evidence_values = validate_evidence(analysis, profile)

        result = MatchScorer.calculate(analysis)

        assessment = {
            "role_family": analysis.role_family,
            "target_seniority": analysis.target_seniority,
            "requirements": [
                {
                    **req.model_dump(),
                    "priority_weight": PRIORITY_WEIGHTS[req.priority],
                    "evidence_value": EVIDENCE_VALUES[req.evidence_level],
                    "evidence_values": evidence_values.get(req.id, []),
                }
                for req in analysis.requirements
            ],
            "eligibility": [e.model_dump() for e in analysis.eligibility],
            "category_breakdown": result["category_breakdown"],
            "missing_core_requirements": result["missing_core_requirements"],
            "unknown_requirements": result["unknown_requirements"],
            "validation_warnings": warnings,
        }

        return {
            "score": result["score"],
            "label": result["label"],
            "confidence": result["confidence"],
            "base_score": result["base_score"],
            "candidate_hash": candidate_hash,
            "jd_hash": jd_hash_value,
            "scoring_version": settings.match_scoring_version,
            "prompt_version": settings.match_prompt_version,
            "model_name": settings.model_name,
            "assessment": assessment,
        }

    def score_application(
        self,
        app_id: int,
        *,
        force: bool = False,
        master_cv_path: str | None = None,
    ) -> dict:
        application = db.get_application(app_id)
        if application is None:
            raise ValueError(f"Application #{app_id} not found")

        _id, _company, _role, jd_path, _cv_path, _job_url, _created_at, _source, _cl_path = application

        if not jd_path or not Path(jd_path).exists():
            raise ValueError("Job description is missing; cannot score.")

        jd_text = _read_jd_text(jd_path)
        if len(normalize_jd_for_hash(jd_text)) < MIN_JD_CHARS:
            raise ValueError("Job description is too short to score reliably.")

        _master_cv, _profile, candidate_hash = self._load_profile(master_cv_path)
        jd_hash_value = jd_hash(jd_text)

        if not force:
            cached = db.find_cached_match(
                app_id,
                candidate_hash,
                jd_hash_value,
                settings.match_scoring_version,
                settings.match_prompt_version,
                settings.model_name,
            )
            if cached:
                logger.info(
                    "Using cached match assessment #%s for application #%s",
                    cached["id"], app_id,
                )
                return {
                    "assessment_id": cached["id"],
                    "score": cached["score"],
                    "label": cached["label"],
                    "confidence": cached["confidence"],
                    "base_score": cached["base_score"],
                    "cached": True,
                    "candidate_hash": cached["candidate_hash"],
                    "jd_hash": cached["jd_hash"],
                    "scoring_version": cached["scoring_version"],
                    "prompt_version": cached["prompt_version"],
                    "model_name": cached["model_name"],
                    "assessment": json.loads(cached["assessment_json"]),
                }

        logger.info("Scoring match for application #%s", app_id)

        result = self.assess_text(jd_text, master_cv_path=master_cv_path)

        assessment_id = db.insert_match_assessment(
            application_id=app_id,
            score=result["score"],
            label=result["label"],
            confidence=result["confidence"],
            base_score=result["base_score"],
            assessment_json=json.dumps(result["assessment"], ensure_ascii=False),
            candidate_hash=result["candidate_hash"],
            jd_hash=result["jd_hash"],
            scoring_version=result["scoring_version"],
            prompt_version=result["prompt_version"],
            model_name=result["model_name"],
        )

        logger.info(
            "Match score #%s: %s %s (confidence=%s, version=%s)",
            app_id, result["score"], result["label"], result["confidence"],
            result["scoring_version"],
        )

        return {
            "assessment_id": assessment_id,
            "cached": False,
            **result,
        }

    def score_job_posting(
        self,
        job_posting_id: int,
        *,
        force: bool = False,
        master_cv_path: str | None = None,
    ) -> dict:
        """Scores a discovered job posting before any application exists.

        Persists the assessment into ``job_match_assessments`` and updates
        the posting's latest score / match_state. Reuses cached assessments
        when candidate hash, JD hash, and scoring identity all match.
        """
        job = db.get_job_posting(job_posting_id)
        if job is None:
            raise ValueError(f"Job posting #{job_posting_id} not found")

        jd_text = job["description"]
        if len(normalize_jd_for_hash(jd_text)) < MIN_JD_CHARS:
            raise ValueError("Job description is too short to score reliably.")

        _master_cv, _profile, candidate_hash = self._load_profile(master_cv_path)
        jd_hash_value = jd_hash(jd_text)

        if not force:
            cached = db.find_cached_job_match(
                job_posting_id,
                candidate_hash,
                jd_hash_value,
                settings.match_scoring_version,
                settings.match_prompt_version,
                settings.model_name,
            )
            if cached:
                logger.info(
                    "Using cached job match assessment #%s for job posting #%s",
                    cached["id"], job_posting_id,
                )
                return {
                    "assessment_id": cached["id"],
                    "score": cached["score"],
                    "label": cached["label"],
                    "confidence": cached["confidence"],
                    "base_score": cached["base_score"],
                    "cached": True,
                    "candidate_hash": cached["candidate_hash"],
                    "jd_hash": cached["jd_hash"],
                    "scoring_version": cached["scoring_version"],
                    "prompt_version": cached["prompt_version"],
                    "model_name": cached["model_name"],
                    "assessment": json.loads(cached["assessment_json"]),
                }

        db.set_job_match_state(job_posting_id, "scoring")
        try:
            result = self.assess_text(jd_text, master_cv_path=master_cv_path)
        except Exception:
            db.set_job_match_state(job_posting_id, "error")
            raise

        assessment_id = db.insert_job_match_assessment(
            job_posting_id=job_posting_id,
            score=result["score"],
            label=result["label"],
            confidence=result["confidence"],
            base_score=result["base_score"],
            assessment_json=json.dumps(result["assessment"], ensure_ascii=False),
            candidate_hash=result["candidate_hash"],
            jd_hash=result["jd_hash"],
            scoring_version=result["scoring_version"],
            prompt_version=result["prompt_version"],
            model_name=result["model_name"],
        )

        db.set_job_latest_match(
            job_posting_id,
            score=result["score"],
            label=result["label"],
            match_state="scored",
        )

        logger.info(
            "Job match score for posting #%s: %s %s (confidence=%s, version=%s)",
            job_posting_id, result["score"], result["label"], result["confidence"],
            result["scoring_version"],
        )

        return {
            "assessment_id": assessment_id,
            "cached": False,
            **result,
        }

    def score_missing_applications(        self,
        *,
        force: bool = False,
        progress=None,
    ) -> dict:
        """Backfills match scores for applications that have none.

        With ``force=True`` every application with a JD is re-scored.
        Applications without a stored JD are skipped (reported, not errors).
        One failing application never stops the batch.

        Returns ``{"scored": int, "skipped_no_jd": int, "errors": [...]}``.
        """
        progress = progress or (lambda message: None)
        apps = db.list_applications_with_status()
        existing = db.get_latest_matches([a["id"] for a in apps])
        targets = [a for a in apps if force or a["id"] not in existing]

        result: dict = {"scored": 0, "skipped_no_jd": 0, "errors": []}
        total = len(targets)
        for index, app in enumerate(targets, start=1):
            jd_path = app.get("jd_path")
            if not jd_path or not Path(jd_path).exists():
                result["skipped_no_jd"] += 1
                logger.info(
                    "Skipping application #%s (no JD file): %s — %s",
                    app["id"], app["company"], app["role"],
                )
                continue
            progress(
                f"Scoring {index}/{total}: {app['company']} — {app['role'][:44]}"
            )
            try:
                outcome = self.score_application(app["id"], force=force)
                result["scored"] += 1
                logger.info(
                    "Backfilled match for application #%s: %s %s",
                    app["id"], outcome["score"], outcome["label"],
                )
            except Exception as exc:  # noqa: BLE001 — per-app isolation
                message = f"#{app['id']} {app['company']} — {app['role'][:40]}: {exc}"
                result["errors"].append(message)
                logger.warning("Match scoring failed for application #%s: %s", app["id"], exc)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Standalone CLI: `./cv-opt score`
# ─────────────────────────────────────────────────────────────────────────────

def run_score_cli(argv: list[str] | None = None) -> int:
    """Backfills match scores from the command line.

    `cv-opt score`            → score applications missing a match score
    `cv-opt score --force`    → re-score every application that has a JD
    `cv-opt score 3 12`       → score specific application ids
    """
    import argparse
    import sys as _sys

    parser = argparse.ArgumentParser(
        prog="cv-opt score",
        description="Generate Match Scores for tracked applications.",
    )
    parser.add_argument(
        "app_ids", nargs="*", type=int, metavar="APP_ID",
        help="Specific application ids to score (default: all missing).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-score even when a cached assessment exists.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Print the result summary as JSON.",
    )
    args = parser.parse_args(argv)

    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=_sys.stdout
    )

    service = MatchService()
    if args.app_ids:
        result: dict = {"scored": 0, "skipped_no_jd": 0, "errors": []}
        total = len(args.app_ids)
        for index, app_id in enumerate(args.app_ids, start=1):
            app = db.get_application(app_id)
            if app is None:
                result["errors"].append(f"application #{app_id}: not found")
                continue
            _id, company, role, jd_path, *_rest = app
            if not jd_path or not Path(jd_path).exists():
                result["skipped_no_jd"] += 1
                print(f"[skip] #{app_id} {company} — {role} (no JD file)")
                continue
            print(f"Scoring {index}/{total}: #{app_id} {company} — {role}")
            try:
                outcome = service.score_application(app_id, force=args.force)
                result["scored"] += 1
                print(
                    f"  → {outcome['score']} {outcome['label']} "
                    f"(confidence={outcome['confidence']}"
                    + (", cached)" if outcome["cached"] else ")")
                )
            except Exception as exc:  # noqa: BLE001
                message = f"#{app_id} {company} — {role}: {exc}"
                result["errors"].append(message)
                print(f"  ✗ {exc}")
    else:
        result = service.score_missing_applications(force=args.force, progress=print)

    if args.json:
        import json as _json

        print(_json.dumps(result, ensure_ascii=False))
        return 1 if result["errors"] else 0

    print()
    print(f"scored:        {result['scored']}")
    print(f"skipped (no JD): {result['skipped_no_jd']}")
    print(f"errors:        {len(result['errors'])}")
    for error in result["errors"][:10]:
        print(f"  - {error}")
    return 1 if result["errors"] else 0
