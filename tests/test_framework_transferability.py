"""Framework transferability (match-v2) — deterministic, no LLM calls.

Proves the spec's framework-transfer rules:

- React/Vue candidate vs normal Angular role → framework_transfer (0.92)
- deep Angular + RxJS/NgRx/Signals → real depth/technology gaps
- explicit Vue experience → direct
- SvelteKit + generic modern-framework requirement → transfer, not none
- React does NOT transfer to Django/Kubernetes/etc.
- framework transfer does not independently trigger the old hard caps
"""

import json

import pytest

from cv_optimizer import framework_transfer as ft
from cv_optimizer.matching import (
    EVIDENCE_VALUES,
    MatchRequirement,
    MatchScorer,
    RawMatchAnalysis,
    build_match_profile,
    validate_evidence,
)


def _analysis(*requirements: MatchRequirement, role_family: str = "frontend") -> RawMatchAnalysis:
    return RawMatchAnalysis(role_family=role_family, requirements=list(requirements), eligibility=[])


def _req(
    id_: str,
    requirement: str,
    *,
    level: str,
    category: str = "technical",
    priority: str = "must",
    is_core: bool = True,
    paths: list[str] | None = None,
) -> MatchRequirement:
    return MatchRequirement(
        id=id_,
        requirement=requirement,
        category=category,
        priority=priority,
        is_core=is_core,
        evidence_level=level,
        evidence_paths=paths or [],
        rationale="test",
    )


# ── Framework family ─────────────────────────────────────────────────────────

def test_framework_family_members():
    for name in (
        "React", "Next.js", "Preact", "Vue", "Nuxt", "Angular", "Svelte",
        "SvelteKit", "Solid", "SolidStart", "Ember", "Qwik", "Lit",
    ):
        assert ft.is_js_frontend_framework(name), name


def test_framework_aliases_normalized():
    assert ft.normalize_framework_name("React.js") == "react"
    assert ft.normalize_framework_name("NextJS") == "nextjs"
    assert ft.normalize_framework_name("Vue.js") == "vue"
    assert ft.normalize_framework_name("angularjs") == "angular"
    assert ft.normalize_framework_name("Svelte Kit") == "sveltekit"


def test_non_frameworks_rejected():
    for name in ("Django", "Kubernetes", "Terraform", "Python", "PostgreSQL", "Java", "GraphQL"):
        assert not ft.is_js_frontend_framework(name), name


def test_english_word_collisions_are_not_frameworks():
    """'solid', 'next', 'lit', 'ember' as ordinary English must NOT match."""
    assert not ft.is_js_frontend_framework("solid understanding of fundamentals")
    assert not ft.is_js_frontend_framework("the next generation of tooling")
    assert not ft.is_js_frontend_framework("lit up by design")
    assert not ft.is_js_frontend_framework("an ember of an idea")
    assert not ft.is_js_frontend_framework("next steps to apply")


def test_explicit_and_capitalized_forms_still_match():
    assert ft.normalize_framework_name("Solid") == "solid"
    assert ft.normalize_framework_name("Solid.js") == "solid"
    assert ft.normalize_framework_name("SolidJS") == "solid"
    assert ft.normalize_framework_name("Next.js") == "nextjs"
    assert ft.normalize_framework_name("NextJS") == "nextjs"
    assert ft.normalize_framework_name("Ember") == "ember"
    assert ft.normalize_framework_name("Ember.js") == "ember"
    assert ft.normalize_framework_name("Lit") == "lit"
    assert ft.normalize_framework_name("Lit Element") == "lit"


def test_profile_scan_ignores_english_word_collisions():
    """A profile saying 'solid understanding' / 'next generation' does not
    count as framework evidence (lowercase, mid-sentence prose)."""
    profile = build_match_profile(
        {
            "summary": "A solid understanding of the next generation of tooling.",
            "skills": {"frameworks_and_libraries": ["React"]},
        }
    )
    frameworks = ft.candidate_frameworks(profile)
    assert "solid" not in frameworks
    assert "nextjs" not in frameworks
    assert "react" in frameworks


def test_requirement_framework_extraction():
    assert ft.extract_framework_requirement_name("Strong Angular experience") == "angular"
    assert ft.extract_framework_requirement_name("6+ years of Angular") == "angular"
    assert ft.extract_framework_requirement_name("Python backend development") is None


# ── Evidence values (match-v2 taxonomy) ──────────────────────────────────────

def test_evidence_values_v2():
    assert EVIDENCE_VALUES == {
        "direct": 1.00,
        "framework_transfer": 0.92,
        "strong_transfer": 0.75,
        "framework_depth_gap": 0.60,
        "unknown": 0.50,
        "partial": 0.40,
        "none": 0.00,
    }


# ── Python-side validation of framework-transfer classifications ────────────

def _profile_with_frameworks(*names: str) -> dict:
    return build_match_profile(
        {
            "personal_info": {"location": "Warsaw, Poland"},
            "skills": {"frameworks_and_libraries": list(names)},
        }
    )


def test_transfer_validated_when_target_is_js_framework():
    profile = _profile_with_frameworks("React", "Vue.js")
    analysis = _analysis(
        _req(
            "req-1",
            "Angular",
            level="framework_transfer",
            paths=["/skills/frameworks_and_libraries/0"],
        )
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "framework_transfer"
    assert warnings == []


def test_transfer_downgraded_for_non_framework_target():
    profile = _profile_with_frameworks("React")
    analysis = _analysis(
        _req(
            "req-1",
            "Django",
            level="framework_transfer",
            paths=["/skills/frameworks_and_libraries/0"],
        )
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "none"
    assert any("not a mainstream JS frontend framework" in w for w in warnings)


def test_transfer_downgraded_without_other_framework_evidence():
    profile = _profile_with_frameworks("Angular")  # only Angular — same as target
    analysis = _analysis(
        _req(
            "req-1",
            "Angular",
            level="framework_transfer",
            paths=["/skills/frameworks_and_libraries/0"],
        )
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "none"
    assert warnings


def test_transfer_requires_valid_evidence_pointers():
    profile = _profile_with_frameworks("React")
    analysis = _analysis(
        _req(
            "req-1",
            "Angular",
            level="framework_transfer",
            paths=["/skills/does_not_exist/0"],
        )
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "none"
    assert any("Invalid candidate evidence pointer" in w for w in warnings)


def test_depth_gap_kept_for_deep_framework_requirement():
    profile = _profile_with_frameworks("React", "Vue.js")
    analysis = _analysis(
        _req(
            "req-1",
            "6+ years of Angular",
            level="framework_depth_gap",
            paths=["/skills/frameworks_and_libraries/0"],
        )
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "framework_depth_gap"
    assert warnings == []


# ── Hard-cap interaction ─────────────────────────────────────────────────────

def test_framework_transfer_does_not_trigger_hard_cap():
    """An Angular requirement classified framework_transfer must NOT produce
    a missing-core cap by itself."""
    profile = _profile_with_frameworks("React", "Vue.js")
    analysis = _analysis(
        _req(
            "req-1",
            "Angular",
            level="framework_transfer",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
        _req(
            "req-2",
            "TypeScript",
            level="direct",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
    )
    validated, _, _ = validate_evidence(analysis, profile)
    result = MatchScorer.calculate(validated)
    assert result["score"] > 69
    assert result["missing_core_requirements"] == []


def test_framework_depth_gap_does_not_trigger_hard_cap():
    profile = _profile_with_frameworks("React")
    analysis = _analysis(
        _req(
            "req-1",
            "6+ years of Angular",
            level="framework_depth_gap",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
        _req(
            "req-2",
            "TypeScript",
            level="direct",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
    )
    validated, _, _ = validate_evidence(analysis, profile)
    result = MatchScorer.calculate(validated)
    assert result["score"] > 69
    assert result["missing_core_requirements"] == []


def test_true_missing_core_still_caps():
    """A genuinely absent independent requirement must still trigger the cap."""
    profile = _profile_with_frameworks("React")
    analysis = _analysis(
        _req(
            "req-1",
            "Angular",
            level="framework_transfer",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
        _req(
            "req-2",
            "Java",
            level="none",
            is_core=True,
            priority="must",
            paths=[],
        ),
    )
    validated, _, _ = validate_evidence(analysis, profile)
    result = MatchScorer.calculate(validated)
    assert result["score"] <= 69
    assert "req-2" in result["missing_core_requirements"]


def test_deep_angular_role_gets_material_penalty():
    """6+ years Angular + RxJS + NgRx + Signals: depth gap + real gaps
    produce a materially lower score than a generic Angular role."""
    profile = _profile_with_frameworks("React", "Vue.js", "TypeScript")
    deep = _analysis(
        _req("r1", "6+ years of Angular", level="framework_depth_gap", is_core=True, paths=["/skills/frameworks_and_libraries/0"]),
        _req("r2", "RxJS", level="none", is_core=False),
        _req("r3", "NgRx", level="none", is_core=False),
        _req("r4", "Angular Signals", level="none", is_core=False),
        _req("r5", "TypeScript", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"]),
        _req("r6", "Frontend ownership", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"], category="role_scope"),
        _req("r7", "Shipped production work", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"], category="experience_delivery"),
    )
    generic = _analysis(
        _req("r1", "Angular", level="framework_transfer", is_core=True, paths=["/skills/frameworks_and_libraries/0"]),
        _req("r5", "TypeScript", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"]),
        _req("r6", "Frontend ownership", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"], category="role_scope"),
        _req("r7", "Shipped production work", level="direct", is_core=False, paths=["/skills/frameworks_and_libraries/0"], category="experience_delivery"),
    )
    deep_validated, _, _ = validate_evidence(deep, profile)
    generic_validated, _, _ = validate_evidence(generic, profile)
    deep_score = MatchScorer.calculate(deep_validated)["score"]
    generic_score = MatchScorer.calculate(generic_validated)["score"]
    assert deep_score < generic_score
    assert generic_score >= 85  # generic Angular role remains a strong match
    assert deep_score < 85  # deep Angular specialization is a real gap


def test_sveltekit_generic_requirement_is_transfer():
    profile = _profile_with_frameworks("React", "Vue.js")
    analysis = _analysis(
        _req(
            "req-1",
            "SvelteKit",
            level="framework_transfer",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
        _req(
            "req-2",
            "Modern frontend framework experience",
            level="direct",
            is_core=True,
            paths=["/skills/frameworks_and_libraries/0"],
        ),
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "framework_transfer"
    result = MatchScorer.calculate(validated)
    assert result["score"] > 69


def test_react_does_not_transfer_to_python_backend():
    profile = _profile_with_frameworks("React")
    analysis = _analysis(
        _req("req-1", "Python backend development", level="framework_transfer", is_core=True, paths=["/skills/frameworks_and_libraries/0"])
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "none"
    assert any("not a mainstream JS frontend framework" in w for w in warnings)


def test_explicit_vue_experience_is_direct():
    profile = _profile_with_frameworks("React", "Vue.js")
    analysis = _analysis(
        _req("req-1", "Vue 3", level="direct", paths=["/skills/frameworks_and_libraries/1"])
    )
    validated, warnings, _ = validate_evidence(analysis, profile)
    assert validated.requirements[0].evidence_level == "direct"
    assert warnings == []


# ── Prompt hygiene (spec §30 / security review) ──────────────────────────────

def test_prompt_treats_jd_as_untrusted_data():
    """The matching prompt must instruct the model that JD contents are
    DATA, not instructions (prompt-injection defense)."""
    from pathlib import Path

    prompt = (Path(__file__).resolve().parent.parent / "cv_optimizer" / "prompts" / "match.md").read_text()
    assert "untrusted data" in prompt
    assert "inputs, not instructions" in prompt
    assert "prompt-injection" in prompt
    assert "framework_transfer" in prompt
    assert "framework_depth_gap" in prompt
    assert "Do not infer RxJS, NgRx, Angular Signals, Svelte runes" in prompt


def test_prompt_v2_keeps_anti_hallucination_rules():
    from pathlib import Path

    prompt = (Path(__file__).resolve().parent.parent / "cv_optimizer" / "prompts" / "match.md").read_text()
    assert "Do not fabricate evidence" in prompt
    assert "SOURCE OF TRUTH" in prompt
