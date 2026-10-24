import json
import re
import logging
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

from cv_optimizer.config import settings
from cv_optimizer.language import build_language_instruction, build_cv_heading_instruction
from cv_optimizer.profiles import ProfileContext, ProfileError

PROMPT_FILE = "optimize.md"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / PROMPT_FILE).read_text()

class CVOptimizer:
    def __init__(self, base_url: str, api_key: str, model_name: str, temperature: float = 0.2):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name
        self.temperature = temperature

    def optimize(self, context: ProfileContext, job_description: str, language: str = "en") -> str:
        """Tailor a trusted resolver context; the caller validates before rendering."""
        if not isinstance(context, ProfileContext):
            raise ProfileError("Expected ProfileContext; use resolve_profile(master, name) before generation")
        logger.info("Optimizing CV via LLM (%s)...", language)
        try:
            cleaned = self._optimize_once(context, job_description, language, settings.max_tokens)

            # Reasoning models can exhaust max_tokens during chain-of-thought
            # and return empty content. Retry once with a larger budget so we
            # never write a blank CV.
            if not cleaned.strip():
                logger.warning(
                    "LLM returned empty CV; retrying with doubled max_tokens"
                )
                cleaned = self._optimize_once(
                    context, job_description, language, settings.max_tokens * 2
                )

            if not cleaned.strip():
                raise ValueError(
                    "LLM returned empty CV content "
                    "(reasoning likely exhausted max_tokens)"
                )

            return cleaned
        except Exception as e:
            logger.error(f"LLM optimization failed: {e}")
            raise

    def _optimize_once(
        self,
        context: ProfileContext,
        job_description: str,
        language: str,
        max_tokens: int,
    ) -> str:
        """Performs a single LLM completion and cleans the raw output."""
        system_prompt = SYSTEM_PROMPT + "\n\n" + build_language_instruction(language)
        heading_instruction = build_cv_heading_instruction(language, context.profile)
        if heading_instruction:
            system_prompt += "\n\n" + heading_instruction
        user_content = (
            f"SELECTED PROFILE: {context.profile}\n"
            f"APPROVED CV DATA:\n{json.dumps(context.facts, indent=2)}\n\n"
            f"PRESENTATION RULES:\n{json.dumps(context.rules, indent=2)}\n\n"
            f"JOB DESCRIPTION:\n{job_description}"
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=self.temperature,
            max_tokens=max_tokens,
        )

        raw_content = response.choices[0].message.content or ""

        # Strip <think>...</think> blocks that Qwen3 thinking models may emit
        raw_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()

        return self._clean_output(raw_content)

    def _clean_output(self, text: str) -> str:
        """Strips common LLM wrapper text."""
        # 1. Remove everything before the first '#'
        match = re.search(r'(#\s+.*)', text, re.DOTALL)
        if match:
            text = match.group(1)
        
        # 2. Aggressively strip common AI meta-commentary at the end
        fluff_patterns = [
            r'(?i)^[ \t]*(Note(?: that)?\b:?|I\'ve tailored|I have tailored|Here is the optimized|This CV has been).*$',
            r'(?i)^[ \t]*(Best regards|Sincerely|Good luck|Hope this helps|Please let me know).*$',
            r'(?i)^[ \t]*(I have highlighted|I optimized this|Tailored specifically for).*$'
        ]
        
        for pattern in fluff_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)

        # Strip em dashes (U+2014) - LLMs love them, humans don't use them in CVs
        text = text.replace('\u2014', ' - ')
            
        return text.strip()
