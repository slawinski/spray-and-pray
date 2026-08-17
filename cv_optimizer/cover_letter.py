import json
import re
import logging
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI
import fitz

logger = logging.getLogger(__name__)

from cv_optimizer.config import settings

PROMPT_FILE = "cover_letter.md"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / PROMPT_FILE).read_text()

# Clean, professional cover letter CSS for PDF generation
COVER_LETTER_CSS = """
body {
    font-family: Helvetica, Arial, sans-serif;
    color: #1a1a1a;
    line-height: 1.6;
    margin: 0;
    padding: 0;
    font-size: 11pt;
}

.header {
    margin-bottom: 30px;
}
.header h1 {
    margin: 0 0 6px 0;
    font-size: 20pt;
    color: #000;
    font-weight: bold;
}
.header p {
    margin: 2px 0;
    font-size: 9.5pt;
    color: #555;
}

.date-block {
    margin-bottom: 24px;
}
.date-block p {
    margin: 3px 0;
    font-size: 10.5pt;
    color: #333;
}

.salutation {
    margin-bottom: 14px;
}
.salutation p {
    font-size: 10.5pt;
    color: #333;
}

.body-text {
    margin-bottom: 14px;
}
.body-text p {
    font-size: 10.5pt;
    line-height: 1.6;
    color: #333;
    margin: 0 0 12px 0;
}

.closing {
    margin-top: 24px;
}
.closing p {
    font-size: 10.5pt;
    color: #333;
    margin: 3px 0;
}
"""


class CoverLetterOptimizer:
    """Generates an ATS-optimized cover letter via LLM."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
    ):
        self.client = OpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
        )
        self.model_name = model_name or settings.model_name
        self.temperature = temperature if temperature is not None else settings.temperature

    def generate(self, master_cv: Dict[str, Any], job_description: str) -> str:
        """Generates a tailored cover letter from master CV and job description."""
        logger.info("Generating cover letter via LLM...")
        try:
            user_content = (
                f"MASTER CV DATA:\n{json.dumps(master_cv, indent=2)}\n\n"
                f"JOB DESCRIPTION:\n{job_description}"
            )
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=self.temperature,
                max_tokens=settings.max_tokens,
            )

            raw_content = response.choices[0].message.content or ""

            # Strip <think>...</think> blocks that reasoning models may emit
            raw_content = re.sub(
                r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
            ).strip()

            cleaned = self._clean_output(raw_content)
            return cleaned

        except Exception as e:
            logger.error(f"LLM cover letter generation failed: {e}")
            raise

    def _clean_output(self, text: str) -> str:
        """Strips common LLM wrapper text and normalizes output."""
        # 1. Remove everything before the first '##' (the name header)
        match = re.search(r"(##\s+.*)", text, re.DOTALL)
        if match:
            text = match.group(1)

        # 2. Strip common AI meta-commentary at the end
        fluff_patterns = [
            r"(?i)\n*(Note:?|Note that|I've tailored|I have tailored|Here is|This cover letter).*$",
            r"(?i)\n*(Best regards|Good luck|Hope this helps|Please let me know).*$",
            r"(?i)\n*(I have highlighted|I tailored this|Tailored specifically for).*$",
        ]

        for pattern in fluff_patterns:
            text = re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)

        # Strip em dashes (U+2014) — LLMs love them, humans don't use them in cover letters
        text = text.replace("\u2014", " - ")

        return text.strip()


class CoverLetterPDFGenerator:
    """Converts a cover letter Markdown to a clean, professional single-column PDF."""

    MAX_BODY_CHARS = 1000

    def generate(self, markdown_text: str, output_path: str) -> None:
        """Generates a professional cover letter PDF from Markdown."""
        logger.info(f"Generating cover letter PDF to {output_path}...")

        try:
            sections = self._parse_sections(markdown_text)

            # Layout configuration
            margin = 60
            page_width = 595
            page_height = 842
            mediabox = fitz.Rect(0, 0, page_width, page_height)

            content_width = page_width - (2 * margin)

            # Build letter HTML
            html_parts = []

            # Header: name + contact
            if "name" in sections or "contact" in sections:
                html_parts.append('<div class="header">')
                if "name" in sections:
                    html_parts.append(f"<h1>{self._escape_html(sections['name'])}</h1>")
                if "contact" in sections:
                    for line in sections["contact"].split("\n"):
                        line = line.strip()
                        if line:
                            html_parts.append(
                                f"<p>{self._safe_contact_html(line)}</p>"
                            )
                html_parts.append("</div>")

            # Date + Re: block
            date_info = sections.get("date", "")
            re_info = sections.get("re", "")
            if date_info or re_info:
                html_parts.append('<div class="date-block">')
                if date_info:
                    html_parts.append(f"<p>{self._escape_html(date_info)}</p>")
                if re_info:
                    html_parts.append(f"<p>{self._escape_html(re_info)}</p>")
                html_parts.append("</div>")

            # Salutation + body + sign-off share the 1000-char budget
            salutation = sections.get("salutation", "")
            closing = sections.get("closing", [])
            overhead = len(salutation) + sum(len(line) for line in closing)

            # Salutation
            if "salutation" in sections:
                html_parts.append('<div class="salutation">')
                html_parts.append(f"<p>{self._escape_html(salutation)}</p>")
                html_parts.append("</div>")

            # Body paragraphs
            if "body" in sections:
                html_parts.append('<div class="body-text">')
                for para in self._trim_body(sections["body"], overhead):
                    html_parts.append(f"<p>{self._escape_html(para)}</p>")
                html_parts.append("</div>")

            # Closing
            if "closing" in sections:
                html_parts.append('<div class="closing">')
                for line in closing:
                    html_parts.append(
                        f"<p>{self._escape_html(line)}</p>"
                    )
                html_parts.append("</div>")

            letter_html = "".join(html_parts)

            # Render to PDF using Story API
            writer = fitz.DocumentWriter(output_path)
            story = fitz.Story(html=letter_html, user_css=COVER_LETTER_CSS)

            more_content = True
            while more_content:
                device = writer.begin_page(mediabox)
                content_rect = fitz.Rect(
                    margin, margin, margin + content_width, page_height - margin
                )
                more_content, _ = story.place(content_rect)
                story.draw(device)
                writer.end_page()

            writer.close()
            logger.info(f"Cover letter PDF generated: {output_path}")

        except Exception as e:
            logger.error(f"Failed to generate cover letter PDF: {e}")
            raise

    def _trim_body(self, paragraphs: list[str], overhead: int = 0) -> list[str]:
        """Trims body paragraphs so that the salutation, body, and sign-off
        together never exceed MAX_BODY_CHARS.

        ``overhead`` is the combined length of the salutation and closing lines,
        which are always preserved. Drops trailing paragraphs that do not fit
        and truncates the first overflowing paragraph at a word boundary.
        """
        budget = self.MAX_BODY_CHARS - overhead
        trimmed: list[str] = []
        used = 0
        for para in paragraphs:
            remaining = budget - used
            if remaining <= 0:
                break
            if len(para) <= remaining:
                trimmed.append(para)
                used += len(para)
                continue
            cut = para[:remaining]
            boundary = cut.rfind(" ")
            if boundary != -1:
                cut = cut[:boundary]
            cut = cut.rstrip(".,;: -")
            if cut:
                trimmed.append(cut)
            break
        return trimmed

    def _parse_sections(self, text: str) -> Dict[str, Any]:
        """Parses the cover letter markdown into structured sections."""
        sections: Dict[str, Any] = {}
        lines = text.split("\n")

        state = "header"
        body_paragraphs: list[str] = []
        closing_lines: list[str] = []
        current_para: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Name header
            if stripped.startswith("## "):
                sections["name"] = stripped[3:].strip()
                state = "header"
                continue

            # Contact heading — capture the next non-empty line as contact info
            if state in ("header", "contact") and stripped.startswith("### "):
                heading = stripped[4:].strip()
                # If the heading itself contains contact info (e.g., "### john@example.com | ...")
                # or is just the word "Contact", defer to next line
                if heading.lower() not in ("contact", "contact info", "contact information", ""):
                    sections["contact"] = heading
                else:
                    state = "contact"
                continue

            # Capture contact info line (after "### Contact")
            if state == "contact":
                if stripped:
                    sections["contact"] = stripped
                    state = "pre_body"
                    continue
                continue  # skip empty lines in contact state

            # Date line (bold in markdown: **Date:** ...)
            if stripped.startswith("**Date:") or stripped.lower().startswith("**date:"):
                sections["date"] = self._strip_markdown_bold(stripped)
                state = "pre_body"
                continue

            # Re: line (bold in markdown: **Re:** ...)
            if stripped.startswith("**Re:") or stripped.lower().startswith("**re:"):
                sections["re"] = self._strip_markdown_bold(stripped)
                state = "pre_body"
                continue

            # Salutation
            if stripped.lower().startswith("dear"):
                sections["salutation"] = stripped
                state = "body"
                continue

            # Closing sign-off
            if stripped.lower() in ("sincerely,", "best regards,", "yours faithfully,", "kind regards,"):
                # Flush any in-progress paragraph to body
                if current_para:
                    body_paragraphs.append(" ".join(current_para))
                    current_para = []
                sections["body"] = body_paragraphs
                state = "closing"
                closing_lines.append(stripped)
                continue

            # Name after sign-off
            if state == "closing":
                if stripped and not stripped.startswith("#"):
                    closing_lines.append(stripped)
                continue

            # Empty line — paragraph break
            if not stripped:
                if current_para:
                    body_paragraphs.append(" ".join(current_para))
                    current_para = []
                continue

            # Body content
            if state in ("body", "pre_body"):
                current_para.append(stripped)

        # Flush remaining
        if current_para:
            body_paragraphs.append(" ".join(current_para))

        if "body" not in sections:
            sections["body"] = body_paragraphs

        if closing_lines:
            sections["closing"] = closing_lines

        return sections

    @staticmethod
    def _strip_markdown_bold(text: str) -> str:
        """Removes all markdown bold markers from text: **foo** → foo."""
        return text.replace("**", "").strip()

    @staticmethod
    def _escape_html(text: str) -> str:
        """Basic HTML escaping for text content."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    _SAFE_URL_SCHEMES = {"http", "https", "mailto", "ftp"}

    @classmethod
    def _convert_links(cls, text: str) -> str:
        """Converts [text](url) markdown links to HTML <a> tags with URL validation."""
        def _safe_link(match: re.Match) -> str:
            link_text = match.group(1)
            url = match.group(2)
            scheme = url.split(":", 1)[0].lower() if ":" in url else ""
            if scheme and scheme not in cls._SAFE_URL_SCHEMES:
                return link_text  # strip dangerous link, keep text
            return f'<a href="{url}">{link_text}</a>'

        return re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            _safe_link,
            text,
        )

    @classmethod
    def _safe_contact_html(cls, text: str) -> str:
        """Escapes HTML in contact text then converts markdown links to safe <a> tags.

        HTML-escapes the text first (handling <, >, &, "), then converts
        remaining [text](url) patterns to href links with scheme validation.
        Since _escape_html does not escape [, ], (, ), the markdown link
        pattern survives escaping intact.
        """
        escaped = cls._escape_html(text)
        return cls._convert_links(escaped)
