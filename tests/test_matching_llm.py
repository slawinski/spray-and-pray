"""MatchAnalyzer LLM-call behavior: empty-content defense and the
thinking-disable fallback. No live network calls — the OpenAI client is
stubbed."""

import json

import pytest

from cv_optimizer import matching
from cv_optimizer.matching import MatchAnalyzer, _parse_json_response


class FakeChoice:
    def __init__(self, content: str, finish_reason: str = "stop", reasoning: str = ""):
        self.message = FakeMessage(content, reasoning)
        self.finish_reason = finish_reason


class FakeMessage:
    def __init__(self, content: str, reasoning: str = ""):
        self.content = content
        self.reasoning_content = reasoning


class FakeResponse:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


VALID_ANALYSIS = json.dumps(
    {
        "role_family": "frontend",
        "target_seniority": "senior",
        "requirements": [
            {
                "id": "req-1",
                "requirement": "React",
                "category": "technical",
                "priority": "must",
                "is_core": True,
                "evidence_level": "direct",
                "evidence_paths": ["/skills/frameworks_and_libraries/0"],
                "rationale": "listed",
            }
        ],
        "eligibility": [],
    }
)


def _analyzer(completions) -> MatchAnalyzer:
    analyzer = MatchAnalyzer.__new__(MatchAnalyzer)
    analyzer.client = FakeClient(completions)
    return analyzer


def test_empty_content_raises_clear_error():
    analyzer = _analyzer(FakeCompletions([FakeResponse("", finish_reason="stop")]))
    with pytest.raises(ValueError) as exc:
        analyzer.analyze("React required. " * 30, {"skills": {}})
    assert "empty content" in str(exc.value)
    assert "finish_reason=stop" in str(exc.value)


def test_thinking_hint_sent_by_default():
    completions = FakeCompletions([FakeResponse(VALID_ANALYSIS)])
    analyzer = _analyzer(completions)
    result = analyzer.analyze("React required. " * 30, {"skills": {}})
    assert result.requirements[0].requirement == "React"
    assert completions.calls[0].get("extra_body") == {"thinking": {"type": "disabled"}}


def test_thinking_rejection_falls_back_without_hint():
    """Providers that reject the `thinking` field fail naming it; retry
    once without the hint."""
    completions = FakeCompletions(
        [
            ValueError("Invalid parameter: 'thinking' is not supported"),
            FakeResponse(VALID_ANALYSIS),
        ]
    )
    analyzer = _analyzer(completions)
    result = analyzer.analyze("React required. " * 30, {"skills": {}})
    assert result.requirements
    assert "extra_body" not in completions.calls[1]


def test_unrelated_error_is_not_swallowed():
    completions = FakeCompletions([RuntimeError("boom")])
    analyzer = _analyzer(completions)
    with pytest.raises(RuntimeError):
        analyzer.analyze("React required. " * 30, {"skills": {}})


def test_parse_json_response_empty_string():
    with pytest.raises(ValueError):
        _parse_json_response("")


def test_parse_json_response_handles_think_tags():
    raw = "<think>some hidden reasoning</think>" + VALID_ANALYSIS
    data = _parse_json_response(raw)
    assert data["role_family"] == "frontend"


def test_truncated_output_retries_with_doubled_budget():
    """finish_reason='length' (hit the token limit) → one retry with 2×
    max_tokens."""
    completions = FakeCompletions(
        [
            FakeResponse(VALID_ANALYSIS[:200], finish_reason="length"),
            FakeResponse(VALID_ANALYSIS, finish_reason="stop"),
        ]
    )
    analyzer = _analyzer(completions)
    result = analyzer.analyze("React required. " * 30, {"skills": {}})
    assert result.requirements[0].requirement == "React"
    assert len(completions.calls) == 2
    assert completions.calls[1]["max_tokens"] == completions.calls[0]["max_tokens"] * 2


def test_overlong_evidence_paths_are_truncated_not_rejected():
    from cv_optimizer.matching import MatchRequirement, RawMatchAnalysis

    analysis = RawMatchAnalysis.model_validate(
        {
            "role_family": "frontend",
            "target_seniority": "senior",
            "requirements": [
                {
                    "id": "req-1",
                    "requirement": "React",
                    "category": "technical",
                    "priority": "must",
                    "is_core": True,
                    "evidence_level": "direct",
                    "evidence_paths": ["/a/0", "/a/1", "/a/2", "/a/3"],
                    "rationale": "x",
                }
            ],
            "eligibility": [
                {
                    "kind": "location_work_model",
                    "requirement": "Remote Europe",
                    "state": "unknown",
                    "evidence_paths": ["/location", "/experience/1", "/experience/2"],
                }
            ],
        }
    )
    assert len(analysis.requirements[0].evidence_paths) == 3
    assert len(analysis.eligibility[0].evidence_paths) == 2
    assert analysis.eligibility[0].kind == "location_work_model"
