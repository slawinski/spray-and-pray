"""Independent, advisory checking of cleaned document Markdown.

Writers never receive exclusions. This checker alone receives both sides of the
eligibility boundary. A pass applies only to the supplied Markdown, not later edits.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from cv_optimizer.config import settings
from cv_optimizer.profiles import ProfileContext, ProfileError


SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "validate_document.md").read_text()


@dataclass(frozen=True)
class ValidationResult:
    """Detailed local warnings plus a content-free notification summary."""

    warnings: tuple[str, ...] = ()
    checker_completed: bool = True

    @property
    def summary(self) -> str:
        if not self.checker_completed:
            return "Content check incomplete; review the document and local logs."
        if self.warnings:
            return "Content check warnings; review the document and local logs."
        return ""


def _contains(text: str, phrase: str) -> bool:
    """Exact phrase, case/whitespace insensitive, not a keyword stem match."""
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"(?!\w)"
    return bool(phrase.strip()) and bool(re.search(pattern, text, re.IGNORECASE))


def _employment_text(markdown: str, document_type: str) -> str:
    """Extract employment claims for literal title and identity checks."""
    employment = []
    section = ""
    for line in markdown.splitlines():
        plain = line.replace("**", "").replace("*", "").strip()
        if document_type == "cover_letter":
            if not re.match(r"^(?:re|subject|dotyczy)\s*:", plain, re.IGNORECASE):
                for sentence in re.split(r"(?<=[.!?])\s+", plain):
                    if re.search(r"\b(?:I (?:worked|served|was)|my (?:role|work)|pracowałem|pracowałam)\b",
                                 sentence, re.IGNORECASE):
                        employment.append(sentence)
            continue
        heading = re.match(r"^##\s+(.+)$", plain)
        if heading:
            section = heading[1].casefold()
        elif section in ("experience", "doświadczenie"):
            employment.append(plain)
    return "\n".join(employment)


def _literal_violations(markdown: str, context: ProfileContext, document_type: str) -> list[str]:
    employment = _employment_text(markdown, document_type)
    violations = []

    allowed_roles = context.facts.get("experience", [])
    allowed_titles = {role.get("title", role.get("role")) for role in allowed_roles}
    # Headers and ledger rows start separate jobs; never combine their dates.
    blocks = re.split(r"(?m)(?=^###\s|^>[ \t]*[^\s>])", employment)
    titles = re.findall(r"(?m)^###\s+(.+)$", employment)
    titles.extend(re.findall(r"(?m)^>[ \t]*([^|\n]+)\|", employment))
    cv_titles = {title.casefold().strip() for title in titles}
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
                 language: str = "en") -> ValidationResult:
        """Return advisory findings; checker failures never reject the document.

        document_type is 'cv' or 'cover_letter'. Call after writer cleanup and
        before rendering/publication. No rewriting or application-level retries.
        """
        if not isinstance(context, ProfileContext):
            raise ProfileError("Expected ProfileContext; use resolve_profile(master, name) before validation")
        if document_type not in ("cv", "cover_letter"):
            return ValidationResult(("Unknown document type; content check skipped",), False)
        if not markdown.strip():
            return ValidationResult(("empty document cannot be checked",), False)
        violations = _literal_violations(markdown, context, document_type)
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
            return ValidationResult(tuple(violations) + (
                f"Checker failed; check provider availability and JSON verdict: {exc}",
            ), False)
        if not verdict["passed"]:
            violations.extend(f"{item['quote']!r}: {item['reason']}" for item in verdict["violations"])
        return ValidationResult(tuple(violations))
