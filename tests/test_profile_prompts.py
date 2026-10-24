"""Public writer contracts, using synthetic prepared contexts and fake completions."""

import json
from types import SimpleNamespace

import pytest

from cv_optimizer.cover_letter import CoverLetterOptimizer
from cv_optimizer.optimizer import CVOptimizer
from cv_optimizer.profiles import ProfileContext, ProfileError


def prepared(profile="it"):
    engineering = profile == "mechanical_engineering"
    return ProfileContext(
        profile,
        {"personal_info": {"name": "Synthetic Candidate"},
         "headline": "Mechanical Engineer" if engineering else "Software Engineer",
         "summary": {"intro": "Approved engineering introduction" if engineering else "Approved IT introduction"},
         "experience": [{"id": "software", "title": "Software Engineer", "company": "EDC",
                         "start_date": "2020", "end_date": "present", "achievements": ["Built APIs."]}]
                       + ([{"id": "design", "title": "Design Engineer", "company": "Synthetic Works",
                            "start_date": "2013", "end_date": "2015",
                            "achievements": ["Designed test fixtures using NX."]}] if engineering else []),
         "skills": {"Languages": ["Python"], **({"CAD": ["NX"]} if engineering else {})},
         "education": ([{"degree": "MSc Mechanical Engineering", "university": "Synthetic University",
                         "start_date": "2011", "end_date": "2013", "specialization": "Turbines",
                         "thesis": "Synthetic thermal study"},
                        {"degree": "BSc Mechanical Engineering", "university": "Synthetic University",
                         "start_date": "2007", "end_date": "2011", "specialization": "Mechanics",
                         "thesis": "Synthetic structures study"}] if engineering else
                       [{"degree": "MSc Mechanical Engineering", "university": "Synthetic University"}])},
        {"role_detail": {"software": "brief" if engineering else "detailed",
                         **({"design": "detailed"} if engineering else {})}},
        {"identities": [{"id": "mechanical", "title": "Life Cycle Data Engineer", "company": "EDC",
                          "start_date": "2015", "end_date": "2019"}],
         "skills": [{"category": "CAD", "value": "CATIA V5"}],
         "achievements": [{"role_id": "mechanical", "value": "Reduced turbine mass by 12%."}],
         "sections": {"positioning": [{"summary": "OTHER PROFILE SECRET"}]}},
    )


class FakeClient:
    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.requests.append(request)
        output = next(self.outputs)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=output))])


def writer(kind, client):
    obj = (CVOptimizer("http://fake", "fake", "fake") if kind == "cv"
           else CoverLetterOptimizer("http://fake", "fake", "fake"))
    obj.client = client
    return obj.optimize if kind == "cv" else obj.generate


@pytest.mark.parametrize("kind", ["cv", "cover_letter"])
def test_writers_reject_raw_master_before_completion(kind):
    client = FakeClient("# Candidate")
    with pytest.raises(ProfileError, match="ProfileContext.*resolve_profile"):
        writer(kind, client)({"summary": "Unrestricted master"}, "Vacancy")
    assert client.requests == []


@pytest.mark.parametrize("kind", ["cv", "cover_letter"])
@pytest.mark.parametrize("profile", ["it", "mechanical_engineering"])
@pytest.mark.parametrize("language", ["en", "pl"])
def test_writer_serializes_only_prepared_facts_and_rules(kind, profile, language):
    heading = "#" if kind == "cv" else "##"
    client = FakeClient(f"{heading} Synthetic Candidate\nPython")
    context = prepared(profile)
    result = writer(kind, client)(context, "Vacancy requires CATIA V5", language)
    assert result == f"{heading} Synthetic Candidate\nPython"
    request = client.requests[0]
    system, user = [item["content"] for item in request["messages"]]
    assert json.dumps(context.facts, indent=2) in user
    assert json.dumps(context.rules, indent=2) in user
    assert profile in user
    for excluded in ("Life Cycle Data Engineer", "Reduced turbine mass", "OTHER PROFILE SECRET"):
        assert excluded not in system + user
    assert user.count("CATIA V5") == 1  # vacancy only, never the excluded skill descriptor
    for expanded_detail in ("BSc Mechanical Engineering", "Synthetic thermal study", "2007"):
        assert (expanded_detail in user) == (profile == "mechanical_engineering")
    if profile == "mechanical_engineering":
        assert '"design": "detailed"' in user
        assert '"software": "brief"' in user
        assert "Design Engineer" in user
        assert "Designed test fixtures using NX." in user
    assert f"TARGET LANGUAGE: {'Polish' if language == 'pl' else 'English'}" in system
    if kind == "cv":
        assert "approved headline" in system
        assert "role_detail" in system
        assert "relevance, not recency" in system
        assert "omit attendance dates" in system
        assert "specializations, and theses" in system
        assert "actual, current title exactly" not in system
        if language == "pl":
            assert "## Edukacja" in system
    elif language == "pl":
        assert "Szanowni Państwo" in system


@pytest.mark.parametrize("kind", ["cv", "cover_letter"])
def test_empty_retry_and_cleanup_through_public_writer(kind):
    heading = "#" if kind == "cv" else "##"
    client = FakeClient("<think>reasoning</think>",
                        f"Preamble\n{heading} Synthetic Candidate\nReact.js — Python\nNote: commentary")
    result = writer(kind, client)(prepared(), "JD")
    assert result == f"{heading} Synthetic Candidate\nReact.js  -  Python"
    assert len(client.requests) == 2
    assert client.requests[1]["max_tokens"] == 2 * client.requests[0]["max_tokens"]


@pytest.mark.parametrize("kind", ["cv", "cover_letter"])
def test_second_empty_output_fails_without_more_retries(kind):
    client = FakeClient("", None)
    with pytest.raises(ValueError, match="empty"):
        writer(kind, client)(prepared(), "JD")
    assert len(client.requests) == 2


@pytest.mark.parametrize("kind", ["cv", "cover_letter"])
@pytest.mark.parametrize("language", ["en", "pl"])
def test_baker_writers_receive_only_selected_sources_and_limits(kind, language):
    from pathlib import Path
    from cv_optimizer.profiles import resolve_profile
    source = json.loads((Path(__file__).resolve().parent.parent / "master_cv.example.json").read_text())
    context = resolve_profile(source, "baker", document_type=kind)
    client = FakeClient("# Jane Example\n## Portfolio\n[Home baking portfolio](https://example.com/baking)")
    result = writer(kind, client)(context, "Commercial ovens and sanitary clearance required", language)
    system, user = [item["content"] for item in client.requests[0]["messages"]]
    assert json.dumps(context.facts, indent=2) in user
    assert "Built React dashboards" not in user and "excluded" not in user
    assert all(term in system for term in ("hobby", "workshops" if kind == "cv" else "Workshops", "sanitary clearance", "syllabus", "professional qualification"))
    assert "[Home baking portfolio](https://example.com/baking)" in result
    if kind == "cv":
        assert "Other Employment" in system and "square-bracket" in system
        if language == "pl":
            assert "## Domowa praktyka piekarska" in system
            assert "## Warsztaty" in system and "## Pozostałe zatrudnienie" in system
