"""Discovery configuration validation tests (malformed config fails loudly)."""

import json

import pytest

from cv_optimizer.discovery.config import DiscoveryConfig, load_config


def test_unknown_keys_rejected():
    with pytest.raises(Exception):
        DiscoveryConfig.model_validate({"max_scores_per_runn": 5})  # typo


def test_negative_budget_rejected():
    with pytest.raises(Exception):
        DiscoveryConfig.model_validate({"max_scores_per_run": 0})


def test_zero_pages_rejected():
    with pytest.raises(Exception):
        DiscoveryConfig.model_validate({"sources": {"serpapi": {"max_pages_per_query": 0}}})


def test_unknown_seniority_level_rejected():
    with pytest.raises(Exception):
        DiscoveryConfig.model_validate({"seniority": {"include": ["mid", "wizard"]}})


def test_example_config_is_valid():
    """job_search.example.json must always parse cleanly."""
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / "job_search.example.json"
    config = DiscoveryConfig.model_validate(json.loads(example.read_text()))
    assert config.minimum_match_score == 85
    assert config.framework_policy == "transferable_js"
    assert config.generation.auto_generate_cv is False
    assert config.generation.auto_generate_cover_letter is False


def test_malformed_json_fails_loudly(tmp_path):
    bad = tmp_path / "job_search.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError) as exc:
        load_config(bad)
    assert "not valid JSON" in str(exc.value)


def test_invalid_fields_fail_loudly(tmp_path):
    bad = tmp_path / "job_search.json"
    bad.write_text(json.dumps({"minimum_match_score": 12345}))
    with pytest.raises(ValueError) as exc:
        load_config(bad)
    assert "invalid" in str(exc.value).lower()


def test_missing_config_uses_defaults(tmp_path):
    config = load_config(tmp_path / "nonexistent.json")
    assert isinstance(config, DiscoveryConfig)
    assert config.minimum_match_score == 85
