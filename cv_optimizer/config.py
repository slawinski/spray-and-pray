import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

def _env_flag(name: str) -> bool:
    """Parses an opt-in env var (1/true/yes/on, case-insensitive)."""
    return os.getenv(name, "false").lower() in ("1", "true", "yes", "on")


class Settings(BaseModel):
    llm_base_url: str = Field(default="https://api.deepseek.com/v1")
    llm_api_key: str = Field(default=os.getenv("DEEPSEEK_API_KEY", ""))
    model_name: str = Field(default="deepseek-v4-pro")
    temperature: float = Field(default=0.1)
    max_tokens: int = Field(default=16384)
    request_timeout: int = Field(default=120)

    master_cv_path: str = Field(default="master_cv.json")
    candidate_photo_path: str = Field(default="candidate.jpeg")
    job_description_path: str = Field(default="job_offer.pdf")
    output_md_path: str = Field(default="optimized_cv.md")
    output_pdf_path: str = Field(default="optimized_cv.pdf")

    # Candidate <-> Job matching score
    # match-v2 introduces framework-transfer evidence levels for mainstream
    # JavaScript frontend frameworks (see docs/specs for Milestone 3 v2).
    # Historical match-v1 assessments remain stored and versioned.
    match_temperature: float = Field(default=0.0)
    match_max_tokens: int = Field(default=8192)
    match_scoring_version: str = Field(default="match-v2")
    match_prompt_version: str = Field(default="match-prompt-v2")

    discord_webhook_url: str | None = Field(default=os.getenv("DISCORD_WEBHOOK_URL"))

    # Automated job discovery (TUI [J], `cv-opt discover`, launchd agent).
    # Opt-in via ENABLE_DISCOVERY=true — off by default so scheduled runs
    # and notifications stay silent until you actually want them.
    enable_discovery: bool = Field(default=_env_flag("ENABLE_DISCOVERY"))

settings = Settings()
