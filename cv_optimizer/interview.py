import json
import re
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from cv_optimizer.config import settings
from cv_optimizer import db
from cv_optimizer.extractor import PDFExtractor

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
GENERATOR_PROMPT = (PROMPTS_DIR / "interview-generator.md").read_text()
EVALUATOR_PROMPT = (PROMPTS_DIR / "interview-evaluator.md").read_text()
LESSON_PROMPT = (PROMPTS_DIR / "lesson-generator.md").read_text()
MASTER_CV_PATH = Path("master_cv.json")
COMPANY_INTEL_PATH = Path("company_intel.json")


def _load_master_cv() -> dict:
    if not MASTER_CV_PATH.exists():
        raise FileNotFoundError(f"Master CV not found at {MASTER_CV_PATH}")
    return json.loads(MASTER_CV_PATH.read_text())


def _load_company_intel(company: str) -> dict | None:
    if not COMPANY_INTEL_PATH.exists():
        return None
    try:
        data = json.loads(COMPANY_INTEL_PATH.read_text())
        companies = data.get("companies", [])
        company_lower = company.lower()
        for entry in companies:
            names = [entry["name"].lower()] + [
                a.lower() for a in entry.get("aliases", [])
            ]
            if any(company_lower in name or name in company_lower for name in names):
                return entry
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse company_intel.json: %s", e)
    return None


def _clean_llm_output(text: str) -> str:
    """Strip think blocks and markdown fences from LLM output."""
    text = re.sub(
        r"<think>.*?</think>", "", text, flags=re.DOTALL
    ).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text: str) -> Any:
    cleaned = _clean_llm_output(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Could not parse JSON from LLM response: {cleaned[:200]}")


def _read_jd_text(jd_path: str) -> str:
    p = Path(jd_path)
    if not p.exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")
    if p.suffix.lower() == ".pdf":
        return PDFExtractor.extract_text(str(p))
    return p.read_text()


def _build_client() -> OpenAI:
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.request_timeout,
        max_retries=2,
    )


class InterviewGenerator:
    def __init__(self) -> None:
        self.client = _build_client()

    def generate(self, app_id: int) -> dict:
        application = db.get_application(app_id)
        if not application:
            raise ValueError(f"Application #{app_id} not found")

        _id, company, role, jd_path, _cv_path, _job_url, _created_at = application

        if not jd_path or not Path(jd_path).exists():
            raise FileNotFoundError(f"JD file not found for application #{app_id} at {jd_path}")

        jd_text = _read_jd_text(jd_path)
        master_cv = _load_master_cv()
        company_intel = _load_company_intel(company)

        user_parts = [
            f"JOB DESCRIPTION:\n{jd_text}",
            f"MASTER CV:\n{json.dumps(master_cv, indent=2)}",
        ]
        if company_intel:
            user_parts.append(
                f"COMPANY INTERVIEW INTEL:\n{json.dumps(company_intel, indent=2)}"
            )

        user_content = "\n\n".join(user_parts)

        logger.info("Generating interview questions for application #%d (%s — %s)", app_id, company, role)
        response = self.client.chat.completions.create(
            model=settings.model_name,
            messages=[
                {"role": "system", "content": GENERATOR_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=settings.max_tokens,
        )

        raw = response.choices[0].message.content or ""
        questions = _parse_json_response(raw)

        if not isinstance(questions, list):
            raise ValueError(f"Expected JSON array, got {type(questions).__name__}")

        session_id = db.create_interview_session(app_id, questions)
        logger.info("Created interview session #%d for application #%d", session_id, app_id)

        return {"session_id": session_id, "questions": questions}


class InterviewEvaluator:
    def __init__(self) -> None:
        self.client = _build_client()

    def evaluate(self, session_id: int) -> dict:
        session = db.get_interview_session(session_id)
        if not session:
            raise ValueError(f"Interview session #{session_id} not found")

        if session["scores_json"] is not None:
            raise ValueError(f"Session #{session_id} already evaluated")

        questions = json.loads(session["questions_json"])
        answers = json.loads(session["answers_json"] or "[]")

        if len(answers) < len(questions):
            raise ValueError(
                f"Not all questions answered ({len(answers)}/{len(questions)})"
            )

        user_content = json.dumps(
            {"questions": questions, "answers": answers}, indent=2
        )

        logger.info("Evaluating interview session #%d", session_id)
        response = self.client.chat.completions.create(
            model=settings.model_name,
            messages=[
                {"role": "system", "content": EVALUATOR_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=settings.max_tokens,
        )

        raw = response.choices[0].message.content or ""
        result = _parse_json_response(raw)

        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object, got {type(result).__name__}")

        db.complete_interview_session(
            session_id,
            scores_json=json.dumps(result.get("evaluations", [])),
            readiness_score=result.get("readiness_score", 0),
            report_text=result.get("report_text", ""),
        )

        logger.info("Evaluated session #%d — readiness: %d", session_id, result.get("readiness_score", 0))
        return result


def generate_lesson(
    concept: str,
    context: str = "",
    session_id: int | None = None,
    app_id: int | None = None,
) -> dict:
    existing = db.find_lesson_by_concept(concept, app_id)
    if existing:
        logger.info("Returning existing lesson #%d for concept '%s'", existing["id"], concept)
        return {"lesson_id": existing["id"], "lesson": json.loads(existing["content_json"])}

    client = _build_client()
    user_parts = [f"CONCEPT: {concept}"]

    if context:
        user_parts.append(f"CONTEXT: {context}")

    jd_text = ""
    if app_id:
        app = db.get_application(app_id)
        if app and app[3] and Path(app[3]).exists():
            jd_text = _read_jd_text(app[3])
            user_parts.append(f"JOB DESCRIPTION (for technology context):\n{jd_text}")

    if not jd_text and session_id:
        sess = db.get_interview_session(session_id)
        if sess:
            s_app = db.get_application(sess["application_id"])
            if s_app and s_app[3] and Path(s_app[3]).exists():
                jd_text = _read_jd_text(s_app[3])
                user_parts.append(f"JOB DESCRIPTION (for technology context):\n{jd_text}")

    user_content = "\n\n".join(user_parts)

    logger.info("Generating lesson for concept '%s'", concept)
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "system", "content": LESSON_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=settings.max_tokens,
    )

    raw = response.choices[0].message.content or ""
    lesson = _parse_json_response(raw)

    if not isinstance(lesson, dict):
        raise ValueError(f"Expected JSON object, got {type(lesson).__name__}")

    lesson_id = db.create_lesson(concept, json.dumps(lesson), session_id, app_id)
    logger.info("Created lesson #%d for concept '%s'", lesson_id, concept)

    return {"lesson_id": lesson_id, "lesson": lesson}
