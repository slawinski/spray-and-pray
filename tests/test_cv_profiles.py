"""The synthetic example is the authoritative prepared-master schema fixture."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from cv_optimizer.profiles import ProfileContext, ProfileError, resolve_profile, validate_profile_name


@pytest.fixture()
def source():
    path = Path(__file__).resolve().parent.parent / "master_cv.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_it_projection_and_education_view(source):
    context = resolve_profile(source, "it")
    assert isinstance(context, ProfileContext)
    assert context.profile == "it"
    assert [r["id"] for r in context.facts["experience"]] == ["software"]
    assert context.facts["education"] == [source["education"][0]]
    assert context.facts["skills"] == source["profiles"]["it"]["skills"]
    assert context.facts["summary"] == source["profiles"]["it"]["summary"]
    assert "profiles" not in context.facts
    assert "profile_shared" not in context.facts
    assert context.facts["personal_info"] == source["personal_info"]
    assert context.facts["languages"] == source["languages"]
    assert context.facts["disclaimer"] == source["disclaimer"]
    assert "SolidWorks" not in json.dumps(context.facts)
    assert "Mechanical Society" not in json.dumps(context.facts)
    assert "Model engines" not in json.dumps(context.facts)


def test_engineering_brief_roles_preserve_dates_attribution_and_source_order(source):
    source["profiles"]["mechanical_engineering"].pop("cv_role_detail", None)
    context = resolve_profile(source, "mechanical_engineering")
    roles = context.facts["experience"]
    assert [r["id"] for r in roles] == ["software", "mechanical"]
    assert context.rules == {"role_detail": {"software": "brief", "mechanical": "detailed"}}
    for role, original in zip(roles, source["experience"]):
        for field in ("title", "company", "start_date", "end_date"):
            assert role[field] == original[field]
    assert roles[0]["achievements"] == [source["experience"][0]["achievements"][0]]
    assert [e["id"] for e in context.facts["education"]] == ["msc-expanded", "bsc"]
    assert context.facts["education"] == source["education"][1:]


def test_cv_ledger_override_preserves_source_it_and_letter_context(source):
    source["profiles"]["mechanical_engineering"].pop("cv_role_detail", None)
    original = deepcopy(source)
    before_it = resolve_profile(source, "it")
    before_engineering = resolve_profile(source, "mechanical_engineering")
    source["profiles"]["mechanical_engineering"]["cv_role_detail"] = {"software": "ledger"}
    context = resolve_profile(source, "mechanical_engineering")
    assert context.rules == {"role_detail": {"software": "ledger", "mechanical": "detailed"}}
    for role, expected in zip(context.facts["experience"], before_engineering.facts["experience"]):
        assert {k: v for k, v in role.items() if k != "achievements"} == {
            k: v for k, v in expected.items() if k != "achievements"}
    assert context.facts["experience"][0]["achievements"] == []
    assert context.facts["experience"][1] == before_engineering.facts["experience"][1]
    assert {"role_id": "software", "value": "Automated reporting with Python."} in context.excluded["achievements"]
    assert resolve_profile(source, "it") == before_it
    assert resolve_profile(source, "mechanical_engineering", document_type="cover_letter") == before_engineering
    assert source["experience"] == original["experience"]


@pytest.mark.parametrize("profile,overrides", [
    ("it", {"software": "ledger"}),
    ("mechanical_engineering", {"missing": "ledger"}),
    ("mechanical_engineering", {"software": "brief"}),
    ("mechanical_engineering", []),
])
def test_invalid_cv_role_overrides_follow_strict_policy_contract(source, profile, overrides):
    source["profiles"][profile]["cv_role_detail"] = overrides
    with pytest.raises(ProfileError):
        resolve_profile(source, "it")


def test_cv_override_must_reference_a_selected_role(source):
    policy = source["profiles"]["mechanical_engineering"]
    policy["cv_role_detail"] = {"software": "ledger"}
    del policy["roles"]["software"]
    with pytest.raises(ProfileError):
        resolve_profile(source, "mechanical_engineering")


def test_unselected_new_facts_and_unknown_fields_never_leak(source):
    before = resolve_profile(source, "it").facts
    source["experience"][1]["achievements"].append("New turbine analysis")
    source["experience"][0]["achievements"].append("Unapproved achievement on selected role")
    source["experience"].append({"id": "new-role", "title": "Secret role", "achievements": []})
    source["skills"]["mechanical"].append("New CAD tool")
    source["skills"]["languages"].append("Unapproved language")
    source["hobbies"].append("Secret hobby")
    source["summary"] = "Unrestricted master narrative"
    source["private_notes"] = "Never send this"
    source["personal_info"]["private_notes"] = "Never send this either"
    source["experience"][0]["private_notes"] = "Role secret"
    source["education"][0]["private_notes"] = "Degree secret"
    source["speaking_and_community"][0]["private_notes"] = "Community secret"
    assert resolve_profile(source, "it").facts == before


def test_selector_order_does_not_rewrite_career_chronology(source):
    policy = source["profiles"]["mechanical_engineering"]
    policy["roles"] = dict(reversed(list(policy["roles"].items())))
    policy["education"].reverse()
    facts = resolve_profile(source, "mechanical_engineering").facts
    assert [r["id"] for r in facts["experience"]] == ["software", "mechanical"]
    assert [e["id"] for e in facts["education"]] == ["msc-expanded", "bsc"]


def test_checker_descriptors_separate_identity_achievements_and_skills(source):
    context = resolve_profile(source, "it")
    excluded = context.excluded
    assert excluded["identities"] == [
        {key: value for key, value in source["experience"][1].items() if key != "achievements"}
    ]
    assert {"role_id": "mechanical", "value": "Designed pump assemblies."} in excluded["achievements"]
    assert {"category": "mechanical", "value": "SolidWorks"} in excluded["skills"]
    engineering = resolve_profile(source, "mechanical_engineering")
    assert engineering.excluded["identities"] == []
    assert {"role_id": "software", "value": "Built React dashboards."} in engineering.excluded["achievements"]
    assert "excluded" not in context.facts
    assert source["profiles"]["mechanical_engineering"]["summary"] not in json.dumps(context.facts)


def test_input_and_returned_contexts_are_independent(source):
    original = deepcopy(source)
    context = resolve_profile(source, "it")
    context.facts["experience"][0]["achievements"].append("Changed")
    context.rules["role_detail"].clear()
    context.excluded["identities"][0]["company"] = "Changed"
    assert source == original
    assert resolve_profile(source, "it").facts["experience"][0]["achievements"] == original["experience"][0]["achievements"]


@pytest.mark.parametrize("value", [None, "", "IT", "auto", "*", [], {}])
def test_unknown_profile_names(value):
    with pytest.raises(ProfileError, match="profile"):
        validate_profile_name(value)


@pytest.mark.parametrize("value", ["it", "mechanical_engineering", "baker"])
def test_known_profile_names(value):
    assert validate_profile_name(value) == value


@pytest.mark.parametrize("mutation", [
    lambda s: s.pop("profiles"),
    lambda s: s.pop("profile_shared"),
    lambda s: s["profiles"].update({"unknown": {}}),
    lambda s: s["profiles"]["it"].update({"include_all": True}),
    lambda s: s["profile_shared"].update({"unknown": []}),
    lambda s: s["experience"].append(deepcopy(s["experience"][0])),
    lambda s: s["education"].append(deepcopy(s["education"][0])),
    lambda s: s["experience"][0].pop("id"),
    lambda s: s["profiles"]["it"]["roles"].update({"missing": {"detail": "brief", "achievements": []}}),
    lambda s: s["profiles"]["it"]["roles"]["software"]["achievements"].append("Invented"),
    lambda s: s["experience"][0]["achievements"].__setitem__(0, "Edited source text"),
    lambda s: s["profiles"]["it"]["roles"]["software"].update({"detail": "all"}),
    lambda s: s["profiles"]["it"]["roles"]["software"].update({"unknown": True}),
    lambda s: s["profiles"]["it"]["skills"]["languages"].append("*"),
    lambda s: s["profiles"]["it"]["skills"].update({"missing": []}),
    lambda s: s["profiles"]["it"]["education"].append("missing"),
    lambda s: s["profiles"]["it"]["education"].append("msc-it"),
    lambda s: s["profiles"]["it"]["hobbies"].append("Invented hobby"),
    lambda s: s["profile_shared"]["personal_info"].append("unknown"),
    lambda s: s["profile_shared"]["languages"][0].update({"proficiency": "Invented"}),
    lambda s: s["profile_shared"].update({"disclaimer": "Invented consent"}),
    lambda s: s["profiles"]["it"].update({"summary": []}),
    lambda s: s["profiles"]["it"].update({"headline": ""}),
    lambda s: s["profiles"]["it"].update({"summary": "   "}),
    lambda s: s["profiles"]["it"]["speaking_and_community"][0].update({"unknown": "Not approved"}),
    lambda s: s["profiles"]["it"]["certifications"][0].update({"name": "Invented certificate"}),
    lambda s: s["profiles"]["it"]["skills"]["languages"].append("Python"),
    lambda s: s["experience"][0]["achievements"].append(s["experience"][0]["achievements"][0]),
])
def test_invalid_policy_fails_closed(source, mutation):
    mutation(source)
    with pytest.raises(ProfileError):
        resolve_profile(source, "it")


def test_summary_dictionary_is_an_approved_snapshot(source):
    summary = {"intro": "Approved IT introduction", "highlights": ["Approved positioning"]}
    source["profiles"]["it"]["summary"] = summary
    assert resolve_profile(source, "it").facts["summary"] == summary


def test_only_prepared_profiles_are_available(source):
    del source["profiles"]["mechanical_engineering"]
    assert resolve_profile(source, "it").profile == "it"
    with pytest.raises(ProfileError, match="mechanical_engineering"):
        resolve_profile(source, "mechanical_engineering")


def test_invalid_other_profile_metadata_also_fails_closed(source):
    source["profiles"]["mechanical_engineering"]["education"] = ["missing"]
    with pytest.raises(ProfileError):
        resolve_profile(source, "it")


def test_optional_sections_require_explicit_selection(source):
    for field in ("speaking_and_community", "certifications", "hobbies"):
        del source["profiles"]["it"][field]
    source["profile_shared"] = {"personal_info": [], "languages": [], "disclaimer": None}
    facts = resolve_profile(source, "it").facts
    for field in ("speaking_and_community", "certifications", "hobbies", "disclaimer"):
        assert field not in facts
    assert facts["personal_info"] == {}
    assert facts["languages"] == []


@pytest.mark.parametrize("document_type", ["cv", "cover_letter"])
def test_baker_projection_is_distinct_and_concise(source, document_type):
    context = resolve_profile(source, "baker", document_type=document_type)
    assert context.facts["home_practice"] == source["home_practice"]
    assert context.facts["workshops"] == source["workshops"]
    assert context.facts["portfolio_links"] == source["portfolio_links"]
    assert context.facts["education"] == [{k: source["education"][0][k] for k in ("id", "degree", "university")}]
    assert context.rules["role_detail"] == {}
    assert context.facts["experience"] == []
    assert context.facts["career_summary"] == source["profiles"]["baker"]["career_summary"]
    assert "Tech Corp" not in json.dumps(context.facts)
    assert "Example Pumps" not in json.dumps(context.facts)
    assert "linkedin" not in context.facts["personal_info"]
    assert "github" not in context.facts["personal_info"]
    assert context.facts["personal_info"]["email"] == source["personal_info"]["email"]
    assert context.facts["personal_info"]["phone"] == source["personal_info"]["phone"]
    assert "frequency" not in context.facts["home_practice"][0]
    assert "start_date" in context.excluded["sections"]["education_fields"][0]
    assert "certifications" not in context.facts


def test_legacy_baker_policy_can_still_select_brief_roles(source):
    del source["profiles"]["baker"]["career_summary"]
    source["profiles"]["baker"]["roles"] = {
        r["id"]: {"detail": "brief", "achievements": []} for r in source["experience"]}
    context = resolve_profile(source, "baker")
    assert [r["id"] for r in context.facts["experience"]] == [r["id"] for r in source["experience"]]
    assert all(not r["achievements"] for r in context.facts["experience"])


@pytest.mark.parametrize("value", ["", "*", [], None])
def test_baker_career_summary_is_approved_nonempty_text(source, value):
    source["profiles"]["baker"]["career_summary"] = value
    with pytest.raises(ProfileError):
        resolve_profile(source, "baker")


def test_baker_career_summary_cannot_reintroduce_role_list(source):
    source["profiles"]["baker"]["roles"] = {"software": {"detail": "brief", "achievements": []}}
    with pytest.raises(ProfileError, match="replaces individual roles"):
        resolve_profile(source, "baker")


def test_baking_additions_preserve_existing_writer_projections(source):
    old = deepcopy(source)
    del old["profiles"]["baker"]
    for section in ("home_practice", "workshops", "portfolio_links"):
        del old[section]
    del old["skills"]["baking"]
    for profile in ("it", "mechanical_engineering"):
        for document_type in ("cv", "cover_letter"):
            before = resolve_profile(old, profile, document_type=document_type)
            after = resolve_profile(source, profile, document_type=document_type)
            assert (before.facts, before.rules) == (after.facts, after.rules)
            for section in ("home_practice", "workshops", "portfolio_links"):
                assert after.excluded["sections"][section] == source[section]
    with pytest.raises(ProfileError, match="not prepared"):
        resolve_profile(old, "baker")


@pytest.mark.parametrize("section", ["home_practice", "workshops", "portfolio_links"])
@pytest.mark.parametrize("failure", ["stale", "duplicate", "ambiguous", "wildcard", "unknown", "wrong_profile"])
def test_baker_snapshot_failures_validate_all_policies(source, section, failure):
    selectors = source["profiles"]["baker"][section]
    if failure == "stale":
        selectors[0][next(iter(selectors[0]))] = "Changed"
    elif failure == "duplicate":
        selectors.append(deepcopy(selectors[0]))
    elif failure == "ambiguous":
        source[section].append(deepcopy(source[section][0]))
    elif failure == "wildcard":
        selectors[0] = "*"
    elif failure == "unknown":
        selectors[0]["unknown"] = "No"
    else:
        source["profiles"]["it"][section] = selectors
    with pytest.raises(ProfileError):
        resolve_profile(source, "it")


def test_baker_omission_and_independence(source):
    context = resolve_profile(source, "baker")
    context.facts["home_practice"][0]["activities"].append("Changed")
    assert "Changed" not in source["home_practice"][0]["activities"]
    for section in ("home_practice", "workshops", "portfolio_links"):
        del source["profiles"]["baker"][section]
    facts = resolve_profile(source, "baker").facts
    assert all(s not in facts for s in ("home_practice", "workshops", "portfolio_links"))
