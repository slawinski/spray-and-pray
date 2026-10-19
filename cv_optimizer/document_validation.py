"""Independent, fail-closed checking of cleaned document Markdown.

Writers never receive exclusions. This checker alone receives both sides of the
eligibility boundary. A pass applies only to the supplied Markdown, not later edits.
"""

import json
import re
from pathlib import Path

from openai import OpenAI

from cv_optimizer.config import settings
from cv_optimizer.profiles import ProfileContext, ProfileError


SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "validate_document.md").read_text()


class DocumentValidationError(ValueError):
    """Document content could not be approved; includes type and correction guidance."""


def _contains(text: str, phrase: str) -> bool:
    """Exact phrase, case/whitespace insensitive, not a keyword stem match."""
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"(?!\w)"
    return bool(phrase.strip()) and bool(re.search(pattern, text, re.IGNORECASE))


def _factual_text(markdown: str, document_type: str) -> tuple[str, str]:
    """Limit literal checks to claims; academic/subject meaning is checked semantically."""
    factual, employment = [], []
    section = ""
    for line in markdown.splitlines():
        plain = line.replace("**", "").replace("*", "").strip()
        if document_type == "cover_letter":
            if not re.match(r"^(?:re|subject|dotyczy)\s*:", plain, re.IGNORECASE):
                # Only unambiguous first-person claims get literal checks.
                # Vacancy needs and less explicit phrasing go to the semantic check.
                for sentence in re.split(r"(?<=[.!?])\s+", plain):
                    if re.search(r"\b(?:I|my|we|pracowałem|pracowałam|korzystam|używam|posiadam)\b",
                                 sentence, re.IGNORECASE):
                        factual.append(sentence)
                    if re.search(r"\b(?:I (?:worked|served|was)|my (?:role|work)|pracowałem|pracowałam)\b",
                                 sentence, re.IGNORECASE):
                        employment.append(sentence)
            continue
        heading = re.match(r"^##\s+(.+)$", plain)
        if heading:
            section = heading[1].casefold()
        elif section not in ("", "education", "edukacja", "wykształcenie", "personal info", "dane osobowe", "dane kontaktowe",
                             "languages", "języki", "gdpr disclaimer", "klauzula rodo"):
            factual.append(plain)
            if section in ("experience", "doświadczenie"):
                employment.append(plain)
    return "\n".join(factual), "\n".join(employment)


def _literal_violations(markdown: str, context: ProfileContext, document_type: str) -> list[str]:
    factual, employment = _factual_text(markdown, document_type)
    violations = []
    allowed_skills = [value for values in context.facts.get("skills", {}).values() for value in values]
    for skill in context.excluded.get("skills", []):
        value = skill["value"]
        if value not in allowed_skills and _contains(factual, value):
            violations.append(f"{value!r}: excluded skill; remove the claim or correct the approved profile")

    allowed_roles = context.facts.get("experience", [])
    allowed_titles = {role.get("title", role.get("role")) for role in allowed_roles}
    # Each role header starts a block. Never combine dates from separate jobs.
    blocks = re.split(r"(?m)(?=^###\s)", employment)
    cv_titles = {match.casefold().strip() for match in re.findall(r"(?m)^###\s+(.+)$", employment)}
    for role in context.excluded.get("identities", []):
        title = role.get("title", role.get("role", ""))
        if document_type == "cv":
            title_claimed = title.casefold() in cv_titles
        else:
            title_claimed = bool(title) and bool(re.search(
                r"(?:\bas\s+(?:an?\s+)?|\bI\s+was\s+(?:an?\s+)?|\bjako\s+)"
                + re.escape(title) + r"(?=\s+(?:at|for|w)\b|[.,;]|$)", employment, re.IGNORECASE,
            ))
        if title and title not in allowed_titles and title_claimed:
            violations.append(f"{title!r}: excluded employment title; remove the entire role, including dates")
        identity = tuple(role.get(key, "") for key in ("company", "start_date", "end_date"))
        allowed_identities = {tuple(item.get(key, "") for key in ("company", "start_date", "end_date"))
                              for item in allowed_roles}
        if all(identity) and identity not in allowed_identities:
            if any(all(_contains(block, value) for value in identity) for block in blocks):
                violations.append(f"{' / '.join(identity)!r}: excluded employment identity; remove the role")
    return violations


def _parse_verdict(content: str) -> dict:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate verdict field {key!r}")
            result[key] = value
        return result

    verdict = json.loads(content, object_pairs_hook=unique_object)
    if (not isinstance(verdict, dict) or set(verdict) != {"passed", "violations"}
            or type(verdict["passed"]) is not bool or not isinstance(verdict["violations"], list)):
        raise ValueError("expected exactly passed:boolean and violations:list")
    for violation in verdict["violations"]:
        if (not isinstance(violation, dict) or set(violation) != {"quote", "reason"}
                or any(not isinstance(violation[key], str) or not violation[key].strip()
                       for key in ("quote", "reason"))):
            raise ValueError("each violation needs a nonempty quote and reason")
    if verdict["passed"] != (not verdict["violations"]):
        raise ValueError("inconsistent passed flag and violations")
    return verdict


class DocumentValidator:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model_name: str | None = None, temperature: float | None = None,
                 *, client=None):
        self.client = client if client is not None else OpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            max_retries=0,
        )
        self.model_name = model_name or settings.model_name
        self.temperature = temperature if temperature is not None else settings.temperature

    def validate(self, markdown: str, context: ProfileContext, document_type: str,
                 language: str = "en") -> None:
        """Return None on approval; raise on violations or an unavailable/invalid check.

        document_type is 'cv' or 'cover_letter'. Call after writer cleanup and
        before rendering/publication. No rewriting or application-level retries.
        """
        if not isinstance(context, ProfileContext):
            raise ProfileError("Expected ProfileContext; use resolve_profile(master, name) before validation")
        if document_type not in ("cv", "cover_letter"):
            raise DocumentValidationError(f"{document_type}: check requires document_type 'cv' or 'cover_letter'")
        if not markdown.strip():
            raise DocumentValidationError(f"{document_type}: empty document cannot be checked")
        violations = _literal_violations(markdown, context, document_type)
        if violations:
            raise DocumentValidationError(f"{document_type}: content check failed: " + "; ".join(violations))
        payload = {"markdown": markdown, "profile": context.profile, "facts": context.facts,
                   "rules": context.rules, "excluded": context.excluded,
                   "document_type": document_type, "language": language}
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                temperature=self.temperature,
                max_tokens=settings.max_tokens,
            )
            verdict = _parse_verdict(response.choices[0].message.content)
        except Exception as exc:
            raise DocumentValidationError(
                f"{document_type}: checker failed; document is not approved. "
                f"Check provider availability and JSON verdict: {exc}"
            ) from exc
        if not verdict["passed"]:
            details = "; ".join(f"{item['quote']!r}: {item['reason']}" for item in verdict["violations"])
            raise DocumentValidationError(f"{document_type}: content check failed: {details}")
