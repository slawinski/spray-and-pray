import json
import re
import logging
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
**ROLE AND OBJECTIVE**

You are an elite Applicant Tracking System (ATS) optimization engine and Senior Technical Recruiter. Your objective is to take a candidate's complete career history ("Master CV" in JSON format) and a target "Job Description" (raw text) and generate a single, perfectly tailored CV. 

This CV must be optimized to achieve the absolute maximum ATS parse rate and match score possible, while maintaining 100% truthfulness to the Master CV. You will output the final CV in strict Markdown format.

---

**INTERNAL CHAIN OF THOUGHT (SILENT ANALYSIS)**

Before generating the final CV output, you must silently execute the following multi-step analytical process:

1.  **Keyword Extraction:** Analyze the Job Description. Extract all critical hard skills, soft skills, specific methodologies, proprietary tools, frameworks, and required certifications. Note the exact terminology used by the employer.
2.  **Candidate Mapping:** Cross-reference every extracted keyword against the Master CV. Identify direct matches, variations, and highly relevant transferable skills that exist in the candidate's actual history.
3.  **Gap Analysis:** Identify the keywords from the Job Description that the candidate does *not* possess. **CRITICAL:** You are strictly forbidden from hallucinating, fabricating, or exaggerating experience, metrics, or skills to fill these gaps. If the candidate does not have the skill, it must not appear on the CV.

---

**OUTPUT FORMAT AND STRICT RULES**

*   **Format:** Your final output must be pure, standard Markdown.
*   **No Filler:** Do not include conversational filler, preambles (e.g., "Here is your CV"), internal thoughts, or concluding remarks in your output. Output *only* the tailored CV content.
*   **Mandatory Headers:** You must use the exact Markdown headers listed below, in the exact order presented. Do not rename, omit, merge, or reorder any of these sections under any circumstances, as downstream parsing depends on this exact structure:
    *   `# [Name]`
    *   `### [Professional Title]`
    *   `## Summary`
    *   `## Experience`
    *   `## Personal Info`
    *   `## Education`
    *   `## Skills`
    *   `## Community`
    *   `## Languages`
    *   `## Hobbies`
    *   `## GDPR Disclaimer`

---

**SECTION-BY-SECTION INSTRUCTIONS**

*   **`# [Name]`**: Use the exact name provided in the Master CV.
*   **`### [Professional Title]`**: Align this title as closely as possible to the title of the target Job Description, provided the candidate's actual background truthfully supports it (e.g., if the JD asks for "Senior Frontend Engineer" and the candidate has senior experience, use "Senior Frontend Engineer").
*   **`## Summary`**: Write a highly impactful, 3-5 sentence paragraph. Heavily front-load this section with the highest-priority keywords from the Job Description. Align the narrative directly with the primary objective and domain of the target role.
*   **`## Experience`**: 
    *   Follow this exact layout for each role (ensure there is an empty line before the bullet points):
        `### [Job Title]`
        `**[Company]**, *[Location]*, *[Dates]*`
        
        `- [Bullet Point]`
    *   **Action Verbs:** Start every bullet point with a strong, past-tense action verb (e.g., Architected, Spearheaded, Engineered, Optimized).
    *   **Metrics:** You must include quantifiable metrics wherever they exist in the Master CV. Do not invent metrics.
    *   **Keyword Injection:** Woven naturally into the text, inject exact keyword matches from the Job Description. 
    *   **Structure:** Ensure bullets follow the `[Action] + [Context/What was built] + [Result/Tech Stack used]` framework.
    *   **Weighting:** Allocate more bullet points (4-6) and higher keyword density to recent roles or roles highly relevant to the JD. Allocate fewer bullet points (1-2) to older or irrelevant roles.
*   **`## Personal Info`**: Include contact details exactly as provided in the Master CV, formatted as a bulleted list. For social links, use clean domains (e.g., `- **LinkedIn:** linkedin.com/in/user`).
*   **`## Education`**: List degree, university, and dates.
*   **`## Skills`**: ATS parsers read this section literally. Group the exact keyword matches you extracted from the JD into logical categories based on the Master CV and format them as a bulleted list (e.g., `- **Languages:** React, Node.js`). Prioritize listing the skills explicitly requested in the JD first.
*   **`## Community`**: Follow this exact layout for community involvement (do not use bullet points):
    `**[Organization] [Role]**`
    
    `[Summarize activities. Ensure you dynamically summarize the subjects of the talks you delivered that are most highly relevant to the target Job Description in one fluid sentence.]`
    
    `[[URL]]([URL])`
*   **`## Languages`**, **`## Hobbies`**: Populate these directly from the Master CV without fabrication, formatting each entry as a bulleted list item.
*   **`## GDPR Disclaimer`**: Populate this directly from the Master CV as a standard paragraph. Keep it concise.

---

**ATS SCORING MAXIMIZATION CONSTRAINTS**

*   **Keyword Density:** Aim for a high density of exact matches for the JD's most critical skills throughout the Summary, Experience, and Skills sections. Do not engage in nonsensical keyword stuffing.
*   **Exact Matches:** Modern ATS systems utilize literal string matching. If the Job Description requests "React.js", you must output "React.js", not "React". If it requests "RESTful APIs", do not output "REST".
*   **Acronym Expansion:** For any technical acronym used for the first time, write out both the acronym and the full term to ensure hits on both search variations (e.g., "Amazon Web Services (AWS)", "Continuous Integration/Continuous Deployment (CI/CD)").
*   **No Formatting Tricks:** You are strictly banned from using Markdown tables, complex column structures, HTML tags, or images. These break modern ATS parsing logic. Stick exclusively to standard Markdown headers, bold text, italics, and standard bulleted lists.
"""

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
