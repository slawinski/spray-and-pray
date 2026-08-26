"""Discovery configuration.

Loaded from ``job_search.json`` (see ``job_search.example.json``). Secrets
(e.g. SERPAPI_API_KEY) live in environment variables, never in the config
file. Validation is strict: malformed configuration fails loudly with a
readable error.
"""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("job_search.json")

DEFAULT_ROLES = [
    "frontend engineer",
    "frontend developer",
    "product engineer",
    "software engineer frontend",
    "full stack engineer javascript",
    "full stack engineer typescript",
    "web engineer",
    "ui engineer",
]

_SENIORITY_LEVELS = {"intern", "junior", "mid", "senior", "staff", "lead", "principal"}


class _BaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeniorityConfig(_BaseConfig):
    include: list[str] = Field(default_factory=lambda: ["mid", "senior"])
    include_unleveled: bool = True
    include_staff: bool = False
    include_lead: bool = False


class WarsawConfig(_BaseConfig):
    onsite: bool = True
    hybrid: bool = True


class RemoteConfig(_BaseConfig):
    poland: bool = True
    europe: bool = True
    eu: bool = False
    eea: bool = False
    emea: bool = True
    worldwide: bool = True


class LocationsConfig(_BaseConfig):
    warsaw: WarsawConfig = Field(default_factory=WarsawConfig)
    remote: RemoteConfig = Field(default_factory=RemoteConfig)


class GenerationConfig(_BaseConfig):
    auto_generate_cv: bool = False
    auto_generate_cover_letter: bool = False
    auto_generate_cv_min_score: int | None = None


class SourceConfig(_BaseConfig):
    enabled: bool = True


class SerpApiConfig(SourceConfig):
    max_pages_per_query: int = Field(default=2, ge=1)


class BoardsConfig(SourceConfig):
    boards: list[str] = Field(default_factory=list)
    sites: list[str] = Field(default_factory=list)


class DiscoveryConfig(_BaseConfig):
    enabled: bool = True
    minimum_match_score: int = Field(default=85, ge=0, le=100)
    max_post_age_days: int = Field(default=30, ge=1)
    max_scores_per_run: int = Field(default=30, ge=1)
    max_fetch_per_run: int | None = Field(default=500, ge=1)

    roles: list[str] = Field(default_factory=lambda: list(DEFAULT_ROLES))

    seniority: SeniorityConfig = Field(default_factory=SeniorityConfig)
    locations: LocationsConfig = Field(default_factory=LocationsConfig)

    framework_policy: Literal["transferable_js"] = "transferable_js"

    priorities: dict[str, str] = Field(default_factory=dict)

    auto_import: bool = True

    generation: GenerationConfig = Field(default_factory=GenerationConfig)

    sources: dict[str, SourceConfig | SerpApiConfig | BoardsConfig] = Field(
        default_factory=lambda: {
            "serpapi": SerpApiConfig(),
            "greenhouse": BoardsConfig(boards=[], sites=[]),
            "lever": BoardsConfig(boards=[], sites=[]),
            "ashby": BoardsConfig(boards=[], sites=[]),
        }
    )

    @model_validator(mode="after")
    def _validate_seniority_levels(self) -> "DiscoveryConfig":
        for level in self.seniority.include:
            if level not in _SENIORITY_LEVELS:
                raise ValueError(f"Unknown seniority level in config: {level!r}")
        return self

    def source_enabled(self, name: str) -> bool:
        cfg = self.sources.get(name)
        return bool(cfg and cfg.enabled)

    def source(self, name: str) -> SourceConfig:
        return self.sources.get(name, SourceConfig())

    def serpapi(self) -> SerpApiConfig:
        cfg = self.sources.get("serpapi", SerpApiConfig())
        return cfg if isinstance(cfg, SerpApiConfig) else SerpApiConfig(**cfg.model_dump())

    def boards_for(self, name: str) -> BoardsConfig:
        cfg = self.sources.get(name, BoardsConfig())
        return cfg if isinstance(cfg, BoardsConfig) else BoardsConfig(**cfg.model_dump())


def load_config(path: Path | str | None = None) -> DiscoveryConfig:
    """Loads discovery configuration, validating malformed input clearly."""
    target = Path(path) if path else CONFIG_PATH
    if not target.exists():
        logger.info("No %s found — using discovery defaults", target)
        return DiscoveryConfig()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Discovery config {target} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Discovery config {target} must contain a JSON object")
    try:
        return DiscoveryConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            f"Discovery config {target} is invalid:\n{exc}"
        ) from exc
