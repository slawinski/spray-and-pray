"""Pure, fail-closed preparation of a shared factual CV for document generation.

``master_cv.example.json`` is the authoritative synthetic schema fixture:

* ``profiles.<name>`` requires an approved ``headline`` (string), ``summary``
  (string or structured dict snapshot), ``roles`` (ID -> detail/achievements),
  ``skills`` (category -> exact values), and ``education`` (stable source IDs).
* Optional community/certification selectors are exact source-entry snapshots;
  hobby selectors are exact strings. Omission selects nothing. Known record
  fields below are the only copyable fields, even in a selected entry.
* ``profile_shared`` requires explicit personal-info field names, exact language
  entry snapshots, and the exact source disclaimer string (or null to omit it).
* Roles use ``detailed``/``brief`` detail rules and exact achievement strings.
  Mechanical ``cv_role_detail`` overrides may mark selected IDs as ``ledger``:
  CVs retain identities only; cover letters keep the original role selections.
  Source ordering is retained, not inferred from titles or rewritten dates.
  Education IDs identify complete views: keep the existing IT MSc record and
  add expanded engineering records beside it, never overwrite the IT view.

Positioning in policy is itself the candidate-approved snapshot, not a reference
to the unrestricted legacy master summary. All other selections must resolve to
source facts. Unknown policy keys, ambiguous references and wildcards fail.

"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class ProfileError(ValueError):
    """The requested profile or its prepared source policy is invalid."""


@dataclass(frozen=True)
class ProfileContext:
    profile: str
    facts: dict[str, Any]
    rules: dict[str, Any]
    excluded: dict[str, Any]


_NAMES = {"it", "mechanical_engineering"}
_CONTACT = {"name", "email", "phone", "linkedin", "github", "website", "location"}
_IDENTITY = {"id", "title", "role", "company", "location", "start_date", "end_date"}
_EDUCATION = {"id", "degree", "university", "location", "start_date", "end_date", "specialization", "thesis"}
_SECTIONS = {
    "speaking_and_community": {
        "organization", "url", "role", "start_date", "end_date", "activities", "talks",
    },
    "certifications": {"name", "issuer", "issue_date", "expiry_date", "url"},
    "languages": {"language", "proficiency"},
}
_REQUIRED = {"headline", "summary", "roles", "skills", "education"}
_OPTIONAL = {"speaking_and_community", "certifications", "hobbies"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def validate_profile_name(value: Any) -> str:
    _require(isinstance(value, str) and value in _NAMES,
             "profile must be 'it' or 'mechanical_engineering'")
    return value


def _mapping(value: Any, where: str) -> dict:
    _require(isinstance(value, dict) and all(isinstance(k, str) for k in value),
             f"{where} must be an object with string keys")
    return value


def _keys(value: Any, required: set, optional: set, where: str) -> dict:
    value = _mapping(value, where)
    _require(required <= value.keys() and value.keys() <= required | optional,
             f"{where}: required keys {sorted(required)}; allowed keys {sorted(required | optional)}")
    return value


def _list(value: Any, where: str) -> list:
    _require(isinstance(value, list), f"{where} must be an explicit list")
    return value


def _text(value: Any, where: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and value != "*",
             f"{where} must be a nonempty string, not a wildcard")
    return value


def _narrative(value: Any, where: str) -> None:
    """Approved snapshots contain only JSON narrative containers and strings."""
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for item in value:
            _narrative(item, where)
        return
    if isinstance(value, dict):
        for item in _mapping(value, where).values():
            _narrative(item, where)
        return
    raise ProfileError(f"{where} must contain only strings, lists and objects")


def _record(value: Any, fields: set, where: str) -> dict:
    value = _mapping(value, where)
    result = {key: deepcopy(item) for key, item in value.items() if key in fields}
    _narrative(result, where)
    return result


def _indexed(value: Any, where: str) -> dict:
    result = {}
    for entry in _list(value, where):
        entry = _mapping(entry, where)
        identity = _text(entry.get("id"), f"{where}.id")
        _require(identity not in result, f"{where}: duplicate ID {identity!r}")
        result[identity] = entry
    return result


def _select(source: list, selectors: Any, where: str) -> list:
    selectors = _list(selectors, where)
    for index, selector in enumerate(selectors):
        _require(selector != "*", f"{where}: wildcards are not allowed")
        _require(selector not in selectors[:index], f"{where}: duplicate selector {selector!r}")
        _require(source.count(selector) == 1,
                 f"{where}: dangling or ambiguous selector {selector!r}; update policy with source edits")
    return deepcopy([item for item in source if item in selectors])


def _snapshots(master: dict, section: str, selectors: Any) -> tuple[list, list]:
    fields = _SECTIONS[section]
    source = [_record(item, fields, section) for item in _list(master.get(section, []), section)]
    for selector in _list(selectors, f"selectors.{section}"):
        _keys(selector, set(), fields, f"selectors.{section}")
    return source, _select(source, selectors, section)


def _prepare(master: dict, profile: str, policy: dict, roles: dict, education: dict,
             document_type: str) -> ProfileContext:
    optional = _OPTIONAL | ({"cv_role_detail"} if profile == "mechanical_engineering" else set())
    policy = _keys(policy, _REQUIRED, optional, f"profiles.{profile}")
    headline = _text(policy["headline"], f"profiles.{profile}.headline")
    summary = policy["summary"]
    _require(isinstance(summary, (str, dict)) and bool(summary),
             f"profiles.{profile}.summary must be an approved string or dict snapshot")
    if isinstance(summary, str):
        _text(summary, f"profiles.{profile}.summary")
    _narrative(summary, f"profiles.{profile}.summary")
    facts = {"headline": headline, "summary": deepcopy(summary)}
    excluded = {"identities": [], "achievements": [], "skills": [], "sections": {}}

    shared = _keys(master.get("profile_shared"), {"personal_info", "languages", "disclaimer"}, set(), "profile_shared")
    contact = _record(master.get("personal_info", {}), _CONTACT, "personal_info")
    selected_contact = _select(list(contact), shared["personal_info"], "profile_shared.personal_info")
    facts["personal_info"] = {key: contact[key] for key in selected_contact}
    _, facts["languages"] = _snapshots(master, "languages", shared["languages"])
    if shared["disclaimer"] is not None:
        _text(shared["disclaimer"], "profile_shared.disclaimer")
        _require(shared["disclaimer"] == master.get("disclaimer"), "profile_shared.disclaimer must match source consent")
        facts["disclaimer"] = shared["disclaimer"]

    role_policy = _mapping(policy["roles"], f"profiles.{profile}.roles")
    _require(role_policy.keys() <= roles.keys(), f"profiles.{profile}.roles contains an unknown role ID")
    cv_detail = _mapping(policy.get("cv_role_detail", {}), f"profiles.{profile}.cv_role_detail")
    _require(cv_detail.keys() <= role_policy.keys(), "cv_role_detail must reference selected role IDs")
    _require(all(value == "ledger" for value in cv_detail.values()),
             "cv_role_detail values must be ledger")
    facts["experience"] = []
    detail = {}
    for role_id, role in roles.items():
        identity = _record(role, _IDENTITY, f"experience.{role_id}")
        achievements = _list(role.get("achievements", []), f"experience.{role_id}.achievements")
        for achievement in achievements:
            _text(achievement, f"experience.{role_id}.achievements")
        selected = []
        if role_id in role_policy:
            selection = _keys(role_policy[role_id], {"detail", "achievements"}, set(), f"roles.{role_id}")
            _require(selection["detail"] in ("detailed", "brief"), f"roles.{role_id}.detail must be detailed or brief")
            selected = _select(achievements, selection["achievements"], f"roles.{role_id}.achievements")
            role_detail = selection["detail"]
            if document_type == "cv" and role_id in cv_detail:
                role_detail = "ledger"
                selected = []
            facts["experience"].append({**identity, "achievements": selected})
            detail[role_id] = role_detail
        else:
            excluded["identities"].append(identity)
        excluded["achievements"].extend(
            {"role_id": role_id, "value": item} for item in achievements if item not in selected
        )

    skills = _mapping(master.get("skills", {}), "skills")
    skill_policy = _mapping(policy["skills"], f"profiles.{profile}.skills")
    _require(skill_policy.keys() <= skills.keys(), f"profiles.{profile}.skills contains an unknown category")
    facts["skills"] = {}
    for category, values in skills.items():
        values = _list(values, f"skills.{category}")
        for value in values:
            _text(value, f"skills.{category}")
        selected = _select(values, skill_policy.get(category, []), f"skills.{category}")
        if category in skill_policy:
            facts["skills"][category] = selected
        excluded["skills"].extend(
            {"category": category, "value": item} for item in values if item not in selected
        )

    education_ids = _select(list(education), policy["education"], f"profiles.{profile}.education")
    facts["education"] = [_record(education[key], _EDUCATION, "education") for key in education_ids]
    excluded["sections"]["education"] = [
        _record(entry, _EDUCATION, "education") for key, entry in education.items() if key not in education_ids
    ]
    for section in ("speaking_and_community", "certifications", "hobbies"):
        if section == "hobbies":
            source = _list(master.get(section, []), section)
            for value in source:
                _text(value, section)
            selected = _select(source, policy.get(section, []), section)
        else:
            source, selected = _snapshots(master, section, policy.get(section, []))
        if section in policy:
            facts[section] = selected
        excluded["sections"][section] = deepcopy([item for item in source if item not in selected])
    return ProfileContext(profile, facts, {"role_detail": detail}, excluded)


def resolve_profile(master: dict, profile: str, *, document_type: str = "cv") -> ProfileContext:
    """Return an independent prepared context, or raise ProfileError (no fallback).

    Every supplied policy is validated, including policies not requested here.
    A profile may be absent until candidate-approved facts/positioning exist.
    CV-only overrides never alter the cover_letter view or canonical master.
    """
    profile = validate_profile_name(profile)
    _require(document_type in ("cv", "cover_letter"), "document_type must be cv or cover_letter")
    master = _mapping(master, "master")
    policies = _mapping(master.get("profiles"), "profiles (prepared metadata required)")
    _require(bool(policies) and policies.keys() <= _NAMES, "profiles contains missing or unknown profile metadata")
    _require(profile in policies, f"profile {profile!r} is not prepared in this master")
    roles = _indexed(master.get("experience"), "experience")
    education = _indexed(master.get("education"), "education")
    contexts = {name: _prepare(master, name, policy, roles, education, document_type)
                for name, policy in policies.items()}
    context = contexts[profile]
    context.excluded["sections"]["positioning"] = [
        {"headline": other.facts["headline"], "summary": other.facts["summary"]}
        for name, other in contexts.items() if name != profile
    ]
    return context
