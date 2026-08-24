import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

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
    match_temperature: float = Field(default=0.0)
    match_max_tokens: int = Field(default=4096)
    match_scoring_version: str = Field(default="match-v1")
    match_prompt_version: str = Field(default="match-prompt-v1")

    discord_webhook_url: str | None = Field(default=os.getenv("DISCORD_WEBHOOK_URL"))

settings = Settings()
