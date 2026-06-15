import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    ollama_api_key: str = Field(default="ollama")
    model_name: str = Field(default="qwen3.6:35b")
    temperature: float = Field(default=0.2)
    num_ctx: int = Field(default=32768)
    
    master_cv_path: str = Field(default="master_cv.json")
    job_description_path: str = Field(default="job_offer.pdf")
    output_md_path: str = Field(default="optimized_cv.md")
    output_pdf_path: str = Field(default="optimized_cv.pdf")

settings = Settings()
