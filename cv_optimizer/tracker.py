import json
import logging
import shutil
import re
from pathlib import Path
from typing import Optional

from cv_optimizer import db
from cv_optimizer.config import settings
from cv_optimizer.extractor import PDFExtractor
from cv_optimizer.optimizer import CVOptimizer
from cv_optimizer.generator import PDFGenerator

logger = logging.getLogger(__name__)

APPLICATIONS_DIR = Path("applications")

VALID_STATUSES = {"applied", "ghosted", "rejected", "offer", "accepted"}
INTERVIEW_PATTERN = re.compile(r"^interview \d+$")


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

def track(company: str, role: str, jd_path: str, master_cv_path: str = None, job_url: str = None) -> int:
    """
    Initializes a new application:
    1. Creates DB record
    2. Generates application directory
    3. Copies JD into the directory
    4. Generates optimized CV inside the directory
    5. Inserts 'applied' then 'ghosted' status (pessimistic default)
    """
    db.init_db()

    jd_source = Path(jd_path)
    if not jd_source.exists():
        raise FileNotFoundError(f"Job description file not found: {jd_path}")

    existing = db.find_application(company, role)
    if existing:
        raise ValueError(
            f"Application already tracked — #{existing['id']}: {existing['company']} — {existing['role']}"
        )

    # 1. Create DB record
    app_id = db.insert_application(company, role, job_url=job_url)
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

    # 4. Generate optimized CV
    try:
        job_description = PDFExtractor.extract_text(str(jd_source))

        actual_master_cv = master_cv_path if master_cv_path else settings.master_cv_path
        with open(actual_master_cv, "r", encoding="utf-8") as f:
            master_cv_data = json.load(f)

        optimizer = CVOptimizer(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model_name=settings.model_name,
            temperature=settings.temperature,
        )
        optimized_md = optimizer.optimize(master_cv_data, job_description)

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

    # 6. Insert pessimistic default statuses
    db.insert_status(app_id, "applied")
    db.insert_status(app_id, "ghosted")

    logger.info(f"Application #{app_id} tracked: applied → ghosted")
    return app_id


def reoptimize(app_id: int, master_cv_path: str = None) -> None:
    """Regenerates the CV for an existing application in-place (no new DB row)."""
    db.init_db()

    app = db.get_application(app_id)
    if app is None:
        raise ValueError(f"Application #{app_id} not found.")

    _id, company, role, jd_path, _cv_path, _job_url, _created_at = app

    if not jd_path or not Path(jd_path).exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    actual_cv = master_cv_path or settings.master_cv_path
    with open(actual_cv, "r", encoding="utf-8") as f:
        master_cv_data = json.load(f)

    jd_source = Path(jd_path)
    job_description = PDFExtractor.extract_text(str(jd_source))

    optimizer = CVOptimizer(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.model_name,
        temperature=settings.temperature,
    )
    optimized_md = optimizer.optimize(master_cv_data, job_description)

    app_dir = _build_app_dir(app_id, company, role)
    app_dir.mkdir(parents=True, exist_ok=True)

    candidate_name = master_cv_data.get("personal_info", {}).get("name", "Candidate")
    cv_base_name = _build_cv_filename(candidate_name, role)

    cv_md_path = app_dir / f"{cv_base_name}.md"
    cv_pdf_path = app_dir / f"{cv_base_name}.pdf"

    cv_md_path.write_text(optimized_md, encoding="utf-8")
    PDFGenerator().generate(optimized_md, str(cv_pdf_path))

    db.update_application(app_id, cv_path=str(cv_pdf_path))

    logger.info(f"CV regenerated for application #{app_id}")


def update_status(application_id: int, status: str) -> None:
    """Appends a new status transition for an existing application.

    Skips the update if the new status is identical to the current latest,
    preventing redundant self-transitions that pollute the Sankey diagram.
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

    db.insert_status(application_id, validated)
    logger.info(f"Application #{application_id}: → {validated}")


def list_all() -> list[tuple]:
    """Returns all applications for display."""
    db.init_db()
    return db.list_applications()
