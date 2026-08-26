import json
import logging
import shutil
import re
import html
from pathlib import Path
from typing import Optional

from cv_optimizer import db
from cv_optimizer.db import status_rank as _status_rank
from cv_optimizer.config import settings
from cv_optimizer.extractor import PDFExtractor
from cv_optimizer.optimizer import CVOptimizer
from cv_optimizer.generator import PDFGenerator
from cv_optimizer.cover_letter import CoverLetterOptimizer, CoverLetterPDFGenerator
from cv_optimizer.language import detect_job_description_language

logger = logging.getLogger(__name__)

APPLICATIONS_DIR = Path("applications")

VALID_STATUSES = {"draft", "applied", "ghosted", "rejected", "offer", "accepted"}
INTERVIEW_PATTERN = re.compile(r"^interview (\d+)$")


def _validate_status(status: str) -> str:
    """Validates and normalizes a status string."""
    normalized = status.lower().strip()
    if normalized in VALID_STATUSES or INTERVIEW_PATTERN.match(normalized):
        return normalized
    raise ValueError(
        f"Invalid status '{status}'. "
        f"Valid: {', '.join(sorted(VALID_STATUSES))}, interview [N]"
    )


def _build_app_dir(app_id: int, company: str, role: str) -> Path:
    """Builds the application directory path using company_role_id format in lower snake case."""
    safe_company = re.sub(r"[^\w\-]", "_", company.lower()).strip('_')
    safe_role = re.sub(r"[^\w\-]", "_", role.lower()).strip('_')
    return APPLICATIONS_DIR / f"{safe_company}_{safe_role}_{app_id}"

from unidecode import unidecode

def _build_cv_filename(name: str, role: str) -> str:
    """Generates a clean filename like First_Last_Role_Title with diacritics normalized."""
    clean_name = unidecode(name)
    clean_role = unidecode(role)
    combined = f"{clean_name} {clean_role}"
    return re.sub(r'[^\w]+', '_', combined).strip('_')

def track(company: str, role: str, jd_path: str, master_cv_path: str = None, job_url: str = None, with_cover_letter: bool = False, source: str = None) -> int:
    """
    Initializes a new application:
    1. Creates DB record
    2. Generates application directory
    3. Copies JD into the directory
    4. Generates optimized CV inside the directory
    5. Sets initial status to 'draft' (pre-application prep; applied+ghosted come later)
    """
    db.init_db()

    # Sanitize inputs: decode any HTML entities (e.g. &amp; → &)
    company = html.unescape(company)
    role = html.unescape(role)

    jd_source = Path(jd_path)
    if not jd_source.exists():
        raise FileNotFoundError(f"Job description file not found: {jd_path}")

    existing = db.find_application(company, role, source=source)
    if existing:
        raise ValueError(
            f"Application already tracked — #{existing['id']}: {existing['company']} — {existing['role']}"
        )

    # 1. Create DB record
    app_id = db.insert_application(company, role, job_url=job_url, source=source)
    logger.info(f"Created application #{app_id}: {company} — {role}")

    # 2. Generate directory
    app_dir = _build_app_dir(app_id, company, role)
    app_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {app_dir}")

    # 3. Copy JD
    clean_role_name = re.sub(r'[^\w\-]', '_', role.lower()).strip('_')
    jd_dest = app_dir / f"{clean_role_name}{jd_source.suffix}"
    
    shutil.copy2(jd_source, jd_dest)
    logger.info(f"Copied JD to {jd_dest}")

    # Persist the JD path early so the match scorer can read it independently.
    db.update_application(app_id, jd_path=str(jd_dest))

    # Best-effort Match Score (isolated; a failure must never block tracking).
    try:
        from cv_optimizer.matching import MatchService
        MatchService().score_application(app_id)
    except Exception as e:
        logger.warning("Match scoring failed for app #%d: %s", app_id, e)

    # 4. Generate optimized CV
    try:
        job_description = PDFExtractor.extract_text(str(jd_source))

        language = detect_job_description_language(job_description).language
        logger.info(
            "Detected JD language: %s", language,
        )

        actual_master_cv = master_cv_path if master_cv_path else settings.master_cv_path
        with open(actual_master_cv, "r", encoding="utf-8") as f:
            master_cv_data = json.load(f)

        optimizer = CVOptimizer(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model_name=settings.model_name,
            temperature=settings.temperature,
        )
        optimized_md = optimizer.optimize(master_cv_data, job_description, language=language)

        candidate_name = master_cv_data.get("personal_info", {}).get("name", "Candidate")
        cv_base_name = _build_cv_filename(candidate_name, role)

        # Save markdown
        cv_md_path = app_dir / f"{cv_base_name}.md"
        cv_md_path.write_text(optimized_md, encoding="utf-8")

        # Save PDF
        cv_pdf_path = app_dir / f"{cv_base_name}.pdf"
        generator = PDFGenerator()
        generator.generate(optimized_md, str(cv_pdf_path))

        logger.info(f"Generated CV at {cv_pdf_path}")
        cv_path_str = str(cv_pdf_path)
    except Exception as e:
        logger.warning(f"CV generation failed (application still tracked): {e}")
        cv_path_str = None

    # 5. Update DB with file paths
    db.update_application(app_id, jd_path=str(jd_dest), cv_path=cv_path_str)

    # 6. Optionally generate cover letter
    if with_cover_letter and cv_path_str:
        try:
            _cl_path = generate_cover_letter(app_id, master_cv_path)
            logger.info(f"Generated cover letter at {_cl_path}")
        except Exception as e:
            logger.warning(f"Cover letter generation failed (CV still tracked): {e}")

    # 7. Set initial status to draft (pre-application prep)
    db.insert_status(app_id, "draft")

    logger.info(f"Application #{app_id} tracked: draft")
    return app_id


def reoptimize(app_id: int, master_cv_path: str = None) -> None:
    """Regenerates the CV for an existing application in-place (no new DB row)."""
    db.init_db()

    app = db.get_application(app_id)
    if app is None:
        raise ValueError(f"Application #{app_id} not found.")

    _id, company, role, jd_path, _cv_path, _job_url, _created_at, _source, _cover_letter_path = app

    if not jd_path or not Path(jd_path).exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    actual_cv = master_cv_path or settings.master_cv_path
    with open(actual_cv, "r", encoding="utf-8") as f:
        master_cv_data = json.load(f)

    jd_source = Path(jd_path)
    job_description = PDFExtractor.extract_text(str(jd_source))

    language = detect_job_description_language(job_description).language
    logger.info("Detected JD language: %s", language)

    optimizer = CVOptimizer(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.model_name,
        temperature=settings.temperature,
    )
    optimized_md = optimizer.optimize(master_cv_data, job_description, language=language)

    # Use the directory that already contains the JD — immune to role-name changes
    app_dir = Path(jd_path).parent
    app_dir.mkdir(parents=True, exist_ok=True)

    candidate_name = master_cv_data.get("personal_info", {}).get("name", "Candidate")
    cv_base_name = _build_cv_filename(candidate_name, role)

    cv_md_path = app_dir / f"{cv_base_name}.md"
    cv_pdf_path = app_dir / f"{cv_base_name}.pdf"

    cv_md_path.write_text(optimized_md, encoding="utf-8")
    PDFGenerator().generate(optimized_md, str(cv_pdf_path))

    db.update_application(app_id, cv_path=str(cv_pdf_path))

    logger.info(f"CV regenerated for application #{app_id}")


def generate_cover_letter(app_id: int, master_cv_path: str = None) -> str:
    """Generates a tailored, ATS-optimized cover letter for an existing application."""
    db.init_db()

    app = db.get_application(app_id)
    if app is None:
        raise ValueError(f"Application #{app_id} not found.")

    _id, company, role, jd_path, _cv_path, _job_url, _created_at, _source, _cover_letter_path = app

    if not jd_path or not Path(jd_path).exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    actual_cv = master_cv_path or settings.master_cv_path
    with open(actual_cv, "r", encoding="utf-8") as f:
        master_cv_data = json.load(f)

    jd_source = Path(jd_path)
    job_description = PDFExtractor.extract_text(str(jd_source))

    language = detect_job_description_language(job_description).language
    logger.info("Detected JD language: %s", language)

    cover_optimizer = CoverLetterOptimizer(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.model_name,
        temperature=settings.temperature,
    )
    cover_letter_md = cover_optimizer.generate(master_cv_data, job_description, language=language)

    # Use the directory that already contains the JD and CV
    app_dir = Path(jd_path).parent
    app_dir.mkdir(parents=True, exist_ok=True)

    candidate_name = master_cv_data.get("personal_info", {}).get("name", "Candidate")
    cl_base_name = _build_cv_filename(candidate_name, role) + "_Cover_Letter"

    cl_md_path = app_dir / f"{cl_base_name}.md"
    cl_pdf_path = app_dir / f"{cl_base_name}.pdf"

    cl_md_path.write_text(cover_letter_md, encoding="utf-8")
    CoverLetterPDFGenerator().generate(cover_letter_md, str(cl_pdf_path))

    db.update_application(app_id, cover_letter_path=str(cl_pdf_path))

    logger.info(f"Cover letter generated for application #{app_id}")
    return str(cl_pdf_path)


def remove_application(app_id: int) -> None:
    """Deletes an application entirely — database records and filesystem directory.

    If the application was auto-imported from a discovered job posting, the
    posting is first marked dismissed so the next discovery run does not
    immediately re-import the same vacancy.
    """
    db.init_db()

    app = db.get_application(app_id)
    if app is None:
        raise ValueError(f"Application #{app_id} not found.")

    _id, company, role, _jd_path, _cv_path, _job_url, _created_at, _source, _cover_letter_path = app

    # 1. Dismiss any linked discovery posting (survives via ON DELETE SET NULL).
    db.dismiss_job_for_application(app_id)

    # 2. Remove filesystem directory
    app_dir = _build_app_dir(app_id, company, role)
    if app_dir.exists():
        shutil.rmtree(app_dir)
        logger.info("Removed directory: %s", app_dir)

    # 3. Remove database records (cascades to status_history, interview_sessions, lessons)
    db.delete_application(app_id)

    logger.info("Application #%d (%s — %s) fully removed", app_id, company, role)


def update_status(application_id: int, status: str) -> None:
    """Records a status transition with flow constraints to prevent circular Sankey diagrams.

    Rules:
      1. No-op: same as current status → skip.
      2. Draft activation: when moving from draft to applied, also insert ghosted
         (the normal pessimistic default kicks in once you actually apply).
      3. Ghosted replacement: if currently ghosted and moving to interview/offer/accepted/rejected,
         delete the ghosted record first (it was a pessimistic default, not a real state).
      4. Undo/backtrack: if the new status ranks lower than any existing transition,
         delete all transitions at or above that rank (undo a mistake cleanly).
      5. Otherwise: just append the new transition.
      6. After backtracking, if the new status matches the remaining last status, skip insert.
    """
    db.init_db()

    app = db.get_application(application_id)
    if app is None:
        raise ValueError(f"Application #{application_id} not found.")

    validated = _validate_status(status)

    current = db.get_latest_status(application_id)
    if current == validated:
        logger.info(
            "Application #%d: skipping redundant %s (already current)",
            application_id, validated,
        )
        return

    new_rank = _status_rank(validated)
    history = db.get_status_history_with_ids(application_id)  # [(id, status, at), ...]

    # Rule 2 — Draft activation: moving from draft → applied kicks in
    # the normal pessimistic ghosted default.
    if current == "draft" and validated == "applied":
        db.insert_status(application_id, "applied")
        db.insert_status(application_id, "ghosted")
        logger.info(
            "Application #%d: activated from draft → applied → ghosted", application_id,
        )
        return

    # Rule 3 — ghosted replacement: pessimistic default was wrong.
    # Ghosted gets replaced by any real outcome (interview, offer, accepted, rejected).
    if current == "ghosted" and new_rank >= _status_rank("interview 1"):
        db.delete_status_by_id(history[-1][0])
        logger.info(
            "Application #%d: replaced ghosted with %s", application_id, validated,
        )
        db.insert_status(application_id, validated)
        return

    # Rule 4 — undo/backtrack: delete all transitions at or above the new rank
    backtracked = False
    for entry in history:
        if _status_rank(entry[1]) >= new_rank:
            db.delete_status_by_id(entry[0])
            backtracked = True

    if backtracked:
        logger.info(
            "Application #%d: backtracked to %s (removed %d transition(s))",
            application_id, validated,
            sum(1 for e in history if _status_rank(e[1]) >= new_rank),
        )

    # After backtracking, the last remaining status may now be identical → skip insert
    remaining = db.get_latest_status(application_id)
    if remaining == validated:
        logger.info(
            "Application #%d: backtrack complete — already at %s",
            application_id, validated,
        )
        return

    db.insert_status(application_id, validated)
    logger.info("Application #%d: → %s", application_id, validated)


def list_all() -> list[tuple]:
    """Returns all applications for display."""
    db.init_db()
    return db.list_applications()
