import json
import re
import logging
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

# PROMPT_FILE = "ats-engineer.md"
# PROMPT_FILE = "ats-engineer-plus.md"
PROMPT_FILE = "recruiter-human-first.md"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / PROMPT_FILE).read_text()

class CVOptimizer:
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float = 0.2, num_ctx: int = 32768):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.temperature = temperature
        self.num_ctx = num_ctx

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
                # Ollama defaults to 4096 context window — far too small for
                # our ~4k-token prompt + expected ~3k-token response.
                extra_body={"options": {"num_ctx": self.num_ctx}}
            )

            # Check if response was truncated due to context window limits
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                logger.error(
                    f"LLM response truncated (finish_reason='length'). "
                    f"Prompt used {response.usage.prompt_tokens} tokens of "
                    f"{self.num_ctx} context window, leaving only "
                    f"{self.num_ctx - response.usage.prompt_tokens} for the response. "
                    f"Increase num_ctx in config."
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
