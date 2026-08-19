"""
Tests for the automatic CV / cover-letter language selection.

Run: python3 tests/test_language.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_optimizer.language import (
    detect_job_description_language,
    resolve_application_language,
    build_language_instruction,
    build_cv_heading_instruction,
    POLISH_LANGUAGE_THRESHOLD,
)


def _assert_language(jd: str, expected: str, label: str) -> None:
    result = detect_job_description_language(jd)
    assert result.language == expected, (
        f"{label}: expected '{expected}', got '{result.language}' "
        f"(detected={result.detected_job_language}, confidence={result.confidence})"
    )


# ═══════════════════════════════════════════════════════════════
# Acceptance scenarios
# ═══════════════════════════════════════════════════════════════

ENGLISH_JD = (
    "We are looking for a Senior Frontend Developer to join our team. "
    "You will build and maintain React applications using TypeScript and Next.js. "
    "We offer a competitive salary, flexible working hours, and a collaborative "
    "environment. Requirements include strong knowledge of React, TypeScript, and "
    "design systems, plus 5+ years of experience building web applications."
)

POLISH_JD = (
    "Poszukujemy Senior Frontend Developera do naszego zespołu. Będziesz odpowiadać "
    "za rozwój aplikacji internetowych oraz współpracę z zespołem produktowym. "
    "Oferujemy pracę zdalną, atrakcyjne wynagrodzenie i benefity. Wymagamy minimum "
    "pięciu lat doświadczenia oraz bardzo dobrej znajomości TypeScript i React."
)

POLISH_WITH_ENGLISH_TECH = (
    "Szukamy Senior Frontend Developera do naszego zespołu.\n\n"
    "Responsibilities:\n"
    "- development of React applications\n"
    "- code review\n"
    "- performance optimization\n\n"
    "Wymagania:\n"
    "- minimum 5 lat doświadczenia\n"
    "- bardzo dobra znajomość TypeScript\n"
    "- doświadczenie z Next.js App Router\n"
    "- React Server Components\n"
    "- Core Web Vitals\n"
    "- CI/CD"
)

ENGLISH_WITH_POLISH_NAMES = (
    "We are hiring for our client Grupa Żywiec, based in Łódź. You will join a team "
    "of experienced engineers and work on large-scale systems. We offer a competitive "
    "salary, flexible working hours, and great benefits. Requirements include strong "
    "React and TypeScript experience, knowledge of design systems, and excellent "
    "communication skills."
)

SHORT_AMBIGUOUS = "Senior Developer (React) - Warszawa"

GERMAN_JD = (
    "Wir suchen einen erfahrenen Entwickler für unser Team. Du arbeitest mit React "
    "und TypeScript an spannenden Projekten. Wir bieten flexible Arbeitszeiten und "
    "ein attraktives Gehalt."
)

FRENCH_JD = (
    "Nous recherchons un développeur frontend senior pour rejoindre notre équipe. "
    "Vous travaillerez avec React et TypeScript sur des projets passionnants."
)


def test_english_jd():
    _assert_language(ENGLISH_JD, "en", "Scenario 1: English JD")


def test_polish_jd():
    _assert_language(POLISH_JD, "pl", "Scenario 2: Polish JD")


def test_polish_with_english_tech():
    _assert_language(POLISH_WITH_ENGLISH_TECH, "pl", "Scenario 3: Polish JD with English tech")


def test_english_with_polish_names():
    _assert_language(ENGLISH_WITH_POLISH_NAMES, "en", "Scenario 4: English JD with Polish names")


def test_short_ambiguous():
    _assert_language(SHORT_AMBIGUOUS, "en", "Scenario 5: short/ambiguous")


def test_german_jd():
    _assert_language(GERMAN_JD, "en", "Scenario 6: German JD")


def test_french_jd():
    _assert_language(FRENCH_JD, "en", "Scenario 6: French JD")


# ═══════════════════════════════════════════════════════════════
# resolve_application_language
# ═══════════════════════════════════════════════════════════════

def test_resolve_pl_above_threshold():
    assert resolve_application_language("pl", 0.93) == "pl"


def test_resolve_pl_below_threshold():
    assert resolve_application_language("pl", 0.4) == "en"


def test_resolve_pl_no_confidence():
    assert resolve_application_language("pl", None) == "en"


def test_resolve_non_polish():
    assert resolve_application_language("de", 0.98) == "en"
    assert resolve_application_language("other", 0.5) == "en"


# ═══════════════════════════════════════════════════════════════
# Detection result structure & confidence
# ═══════════════════════════════════════════════════════════════

def test_result_fields():
    result = detect_job_description_language(POLISH_JD)
    assert result.language == "pl"
    assert result.detected_job_language == "pl"
    assert 0.0 <= result.confidence <= 1.0


def test_confident_polish_has_high_confidence():
    result = detect_job_description_language(POLISH_JD)
    assert result.confidence >= POLISH_LANGUAGE_THRESHOLD


def test_single_polish_proper_noun_does_not_flip():
    # A lone Polish company name in otherwise English prose stays English.
    _assert_language("Work at Żabka as a frontend engineer.", "en", "lone Polish noun")


# ═══════════════════════════════════════════════════════════════
# build_language_instruction
# ═══════════════════════════════════════════════════════════════

def test_instruction_english():
    instruction = build_language_instruction("en")
    assert "TARGET LANGUAGE: English" in instruction
    assert "Polish" not in instruction


def test_instruction_polish():
    instruction = build_language_instruction("pl")
    assert "TARGET LANGUAGE: Polish" in instruction
    assert "Do not invent skills or experience" in instruction


def test_cv_heading_instruction_polish():
    instruction = build_cv_heading_instruction("pl")
    assert "## Podsumowanie" in instruction
    assert "## Doświadczenie" in instruction
    assert "## Klauzula RODO" in instruction


def test_cv_heading_instruction_english_empty():
    assert build_cv_heading_instruction("en") == ""


if __name__ == "__main__":
    tests = [
        test_english_jd,
        test_polish_jd,
        test_polish_with_english_tech,
        test_english_with_polish_names,
        test_short_ambiguous,
        test_german_jd,
        test_french_jd,
        test_resolve_pl_above_threshold,
        test_resolve_pl_below_threshold,
        test_resolve_pl_no_confidence,
        test_resolve_non_polish,
        test_result_fields,
        test_confident_polish_has_high_confidence,
        test_single_polish_proper_noun_does_not_flip,
        test_instruction_english,
        test_instruction_polish,
        test_cv_heading_instruction_polish,
        test_cv_heading_instruction_english_empty,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ {test.__name__}: {e}")
    print(f"\n{'='*50}")
    print(f"✓ {passed} passed, ✗ {failed} failed")
    print(f"{'='*50}")
    raise SystemExit(1 if failed else 0)
