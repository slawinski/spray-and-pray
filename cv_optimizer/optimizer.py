import json
import re
import logging
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

from cv_optimizer.config import settings

PROMPT_FILE = "optimize.md"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / PROMPT_FILE).read_text()

class CVOptimizer:
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float = 0.2):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.temperature = temperature

    def optimize(self, master_cv: Dict[str, Any], job_description: str) -> str:
        """Sends CV and job description to LLM for optimization."""
        logger.info("Optimizing CV via LLM...")
        try:
            user_content = (
                f"MASTER CV DATA:\n{json.dumps(master_cv, indent=2)}\n\n"
                f"JOB DESCRIPTION:\n{job_description}"
            )
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=self.temperature,
                max_tokens=settings.max_tokens,
            )

            raw_content = response.choices[0].message.content or ""

            # Strip <think>...</think> blocks that Qwen3 thinking models may emit
            raw_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()

            cleaned = self._clean_output(raw_content)
            return cleaned
        except Exception as e:
            logger.error(f"LLM optimization failed: {e}")
            raise

    def _clean_output(self, text: str) -> str:
        """Strips common LLM wrapper text."""
        # 1. Remove everything before the first '#'
        match = re.search(r'(#\s+.*)', text, re.DOTALL)
        if match:
            text = match.group(1)
        
        # 2. Aggressively strip common AI meta-commentary at the end
        fluff_patterns = [
            r'(?i)\n*(Note:?|Note that|I\'ve tailored|I have tailored|Here is the optimized|This CV has been).*$',
            r'(?i)\n*(Best regards|Sincerely|Good luck|Hope this helps|Please let me know).*$',
            r'(?i)\n*(I have highlighted|I optimized this|Tailored specifically for).*$'
        ]
        
        for pattern in fluff_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)
            
        return text.strip()
