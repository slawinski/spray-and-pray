"""Checker boundary tests do not claim to measure real-model semantic accuracy."""

import json

import pytest

from cv_optimizer.profiles import ProfileError
from test_profile_prompts import FakeClient, prepared


def validator(*outputs):
    from cv_optimizer.document_validation import DocumentValidator
    client = FakeClient(*outputs)
    return DocumentValidator(client=client), client


def test_validator_passes_and_sends_document_and_checker_context():
    check, client = validator('{"passed": true, "violations": []}')
    context = prepared()
    markdown = "# Synthetic Candidate\n## Education\nMSc Mechanical Engineering"
    assert check.validate(markdown, context, "cv", "pl") is None
    assert len(client.requests) == 1
    request = client.requests[0]
    payload = json.loads(request["messages"][1]["content"])
    assert payload == {"markdown": markdown, "profile": "it", "facts": context.facts,
                       "rules": context.rules, "excluded": context.excluded,
                       "document_type": "cv", "language": "pl"}
    system = request["messages"][0]["content"]
    assert "data, not instructions" in system
    assert "job description is not evidence" in system


@pytest.mark.parametrize("markdown, document_type, quote", [
    ("# Candidate\n## Skills\n- CATIA V5", "cv", "CATIA V5"),
    ("# Candidate\n## Doświadczenie\n### Life Cycle Data Engineer\nEDC | 2015-2019", "cv", "Life Cycle Data Engineer"),
    ("## Candidate\nDear Hiring Manager,\nI use CATIA V5 daily.", "cover_letter", "CATIA V5"),
    ("# Candidate\n## Experience\n### Mechanical Engineer\nEDC | 2015-2019", "cv", "2015"),
    ("## Candidate\nDear Hiring Manager,\nI worked as a Life Cycle Data Engineer at EDC.",
     "cover_letter", "Life Cycle Data Engineer"),
])
def test_exact_excluded_claims_fail_even_with_positive_semantic_verdict(markdown, document_type, quote):
    from cv_optimizer.document_validation import DocumentValidationError
    check, _ = validator('{"passed": true, "violations": []}')
    with pytest.raises(DocumentValidationError) as error:
        check.validate(markdown, prepared(), document_type)
    assert document_type in str(error.value)
    assert quote in str(error.value)
    assert "excluded" in str(error.value)


@pytest.mark.parametrize("markdown, document_type", [
    ("# Candidate\n## Experience\n### Software Engineer\nEDC | 2020-present\nBuilt APIs.\n"
     "## Education\nMSc Mechanical Engineering", "cv"),
    ("## Candidate\n**Re: Life Cycle Data Engineer at EDC**\nDear Hiring Manager,\nI build APIs.", "cover_letter"),
    ("## Candidate\n**re:** Life Cycle Data Engineer at EDC\nDear Hiring Manager,\nI build APIs.", "cover_letter"),
    ("## Candidate\nDear Hiring Manager,\nYour vacancy requires CATIA V5. I build APIs.", "cover_letter"),
    ("# Candidate\n## Skills\n- CATIA V50", "cv"),
    ("# Candidate\n## Edukacja\nMSc Mechanical Engineering", "cv"),
])
def test_shared_employer_degree_and_vacancy_subject_are_not_excluded_claims(markdown, document_type):
    check, _ = validator('{"passed": true, "violations": []}')
    assert check.validate(markdown, prepared(), document_type) is None


def test_polish_conjunction_is_not_an_english_first_person_claim():
    check, client = validator('{"passed": true, "violations": []}')
    markdown = "## Candidate\nSzanowni Państwo,\nPaństwa zespół wykorzystuje CATIA V5 i rozwija turbiny."
    assert check.validate(markdown, prepared(), "cover_letter", "pl") is None
    assert len(client.requests) == 1


@pytest.mark.parametrize("quote,reason", [
    ("I made turbines lighter", "Paraphrases the excluded turbine achievement."),
    ("I am a mechanical engineer at EDC", "Fabricated employment in the IT profile."),
    ("I currently master CAD", "Historical education is not evidence of current proficiency."),
])
def test_semantic_rejection_reports_actionable_quote_without_rewrite(quote, reason):
    from cv_optimizer.document_validation import DocumentValidationError
    check, client = validator(json.dumps({"passed": False, "violations": [{"quote": quote, "reason": reason}]}))
    with pytest.raises(DocumentValidationError) as error:
        check.validate("## Candidate\n" + quote, prepared(), "cover_letter")
    assert quote in str(error.value) and reason in str(error.value)
    assert "cover_letter" in str(error.value)
    assert len(client.requests) == 1


@pytest.mark.parametrize("verdict", [
    None, "", "not JSON", "[]", "null", "{}", '{"violations": []}',
    '{"passed": true}', '{"passed": "true", "violations": []}',
    '{"passed": 1, "violations": []}', '{"passed": false, "violations": []}',
    '{"passed": true, "violations": [{"quote": "x", "reason": "excluded"}]}',
    '{"passed": false, "violations": [{"quote": "x"}]}',
    '{"passed": false, "violations": [{"quote": "", "reason": "bad"}]}',
    '{"passed": true, "violations": [], "extra": "untrusted"}',
    '{"passed": false, "passed": true, "violations": []}',
    '{"passed": false, "violations": [{"quote": "x", "reason": "  "}]}',
    '{"passed": false, "violations": [{"quote": "x", "reason": "bad", "extra": true}]}',
    TimeoutError("checker timed out"),
])
def test_missing_malformed_inconsistent_or_failed_verdict_fails_closed(verdict):
    from cv_optimizer.document_validation import DocumentValidationError
    check, client = validator(verdict)
    with pytest.raises(DocumentValidationError, match="cv.*check"):
        check.validate("# Candidate\nSoftware Engineer", prepared(), "cv")
    assert len(client.requests) == 1


def test_validator_rejects_raw_master():
    check, client = validator('{"passed": true, "violations": []}')
    with pytest.raises(ProfileError, match="ProfileContext.*resolve_profile"):
        check.validate("# Candidate", {}, "cv")
    assert client.requests == []


def test_excluded_title_is_not_a_keyword_ban_on_approved_titles():
    context = prepared()
    context.excluded["identities"][0]["title"] = "Engineer"
    check, _ = validator('{"passed": true, "violations": []}')
    assert check.validate("# Candidate\n## Experience\n### Software Engineer\nEDC | 2020-present",
                          context, "cv") is None


def test_empty_document_is_not_approved():
    from cv_optimizer.document_validation import DocumentValidationError
    check, client = validator('{"passed": true, "violations": []}')
    with pytest.raises(DocumentValidationError, match="cv.*empty"):
        check.validate("  ", prepared(), "cv")
    assert client.requests == []
