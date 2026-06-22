import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load variables from .env into os.environ
load_dotenv()

class Settings(BaseModel):
    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    ollama_api_key: str = Field(default="ollama")
    model_name: str = Field(default="qwen3.6:35b")
    temperature: float = Field(default=0.1)
    num_ctx: int = Field(default=32768)
    
    master_cv_path: str = Field(default="master_cv.json")
    job_description_path: str = Field(default="job_offer.pdf")
    output_md_path: str = Field(default="optimized_cv.md")
    output_pdf_path: str = Field(default="optimized_cv.pdf")
    
    discord_webhook_url: str | None = Field(default=os.getenv("DISCORD_WEBHOOK_URL"))

settings = Settings()
