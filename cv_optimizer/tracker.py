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
from cv_optimizer.profiles import resolve_profile, validate_profile_name
from cv_optimizer.document_validation import DocumentValidator
from cv_optimizer.documents import publish_document

logger = logging.getLogger(__name__)

APPLICATIONS_DIR = Path("applications")

VALID_STATUSES = {"draft", "applied", "ghosted", "withdrawn", "rejected", "offer", "accepted"}
INTERVIEW_PATTERN = re.compile(r"^interview (\d+)$")


def _has_engagement(history: list[tuple]) -> bool:
    """True if the process advanced past the initial post-apply wait.

    Used to tell the two ghosted meanings apart: the pessimistic default
    sitting right behind 'applied' (no engagement yet — withdrawing is
    allowed and swaps it out) vs. real employer silence after interviews
    or an offer (withdrawing is blocked).
    """
    return any(
        entry[1] == "offer" or INTERVIEW_PATTERN.match(entry[1])
        for entry in history
    )


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

def track(company: str, role: str, jd_path: str, master_cv_path: str = None, job_url: str = None, with_cover_letter: bool = False, source: str = None, *, cv_profile: str = None) -> int:
    """
    Initializes a new application:
    1. Creates DB record
    2. Generates application directory
    3. Copies JD into the directory
    4. Generates optimized CV inside the directory
    5. Sets initial status to 'draft' (pre-application prep; applied+ghosted come later)
    """
    cv_profile = validate_profile_name(cv_profile)
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
    app_id = db.insert_application(company, role, job_url=job_url, source=source, cv_profile=cv_profile)
    selection = db.get_application_profile(app_id)
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
        cv_path_str = _generate_document(app_id, master_cv_path, "cv", selection)
    except Exception as e:
        logger.warning(f"CV generation failed (application still tracked): {e}")
        cv_path_str = None

    # 5. Optionally generate cover letter against the initial selection/revision
    if with_cover_letter and cv_path_str:
        try:
            _cl_path = _generate_document(app_id, master_cv_path, "cover_letter", selection)
            logger.info(f"Generated cover letter at {_cl_path}")
        except Exception as e:
            logger.warning(f"Cover letter generation failed (CV still tracked): {e}")

    # 6. Set initial status to draft (pre-application prep)
    db.insert_status(app_id, "draft")

    logger.info(f"Application #{app_id} tracked: draft")
    return app_id


def reoptimize(app_id: int, master_cv_path: str = None) -> None:
    """Regenerates the CV for an existing application in-place (no new DB row)."""
    _generate_document(app_id, master_cv_path, "cv")
    logger.info(f"CV regenerated for application #{app_id}")


def generate_cover_letter(app_id: int, master_cv_path: str = None) -> str:
    """Generates a tailored, ATS-optimized cover letter for an existing application."""
    return _generate_document(app_id, master_cv_path, "cover_letter")


def _generate_document(app_id: int, master_cv_path: str, document_type: str,
                       expected_selection: tuple[str, int] | None = None) -> str:
    """Resolve, write, check and publish against one persisted selection snapshot."""
    db.init_db()

    app = db.get_application(app_id)
    if app is None:
        raise ValueError(f"Application #{app_id} not found.")

    _id, company, role, jd_path, _cv_path, _job_url, _created_at, _source, _cover_letter_path = app

    profile, revision = db.get_application_profile(app_id)
    if profile is None:
        raise ValueError("Select an application profile before generating documents")
    if expected_selection is not None and (profile, revision) != expected_selection:
        raise ValueError("Application profile/revision changed; generate documents explicitly")

    if not jd_path or not Path(jd_path).exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    actual_cv = master_cv_path or settings.master_cv_path
    with open(actual_cv, "r", encoding="utf-8") as f:
        context = resolve_profile(json.load(f), profile)

    jd_source = Path(jd_path)
    job_description = PDFExtractor.extract_text(str(jd_source))

    language = detect_job_description_language(job_description).language
    logger.info("Detected JD language: %s", language)

    optimizer_type = CVOptimizer if document_type == "cv" else CoverLetterOptimizer
    optimizer = optimizer_type(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.model_name,
        temperature=settings.temperature,
    )
    write = optimizer.optimize if document_type == "cv" else optimizer.generate
    markdown = write(context, job_description, language=language)
    DocumentValidator().validate(markdown, context, document_type, language)

    candidate_name = context.facts.get("personal_info", {}).get("name", "Candidate")
    base_name = _build_cv_filename(candidate_name, role)
    if document_type == "cover_letter":
        base_name += "_Cover_Letter"
    pdf_path = Path(jd_path).parent / f"{base_name}.pdf"
    renderer = PDFGenerator() if document_type == "cv" else CoverLetterPDFGenerator()
    return publish_document(app_id, profile, revision, markdown, pdf_path,
                            renderer.generate, document_type)


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
      2. Draft activation: "draft" is pre-application prep, so the funnel must
         always pass through "applied". Moving from draft to any real status
         auto-activates by inserting applied (plus the pessimistic ghosted
         default), so draft never skips straight to interview/rejection.
      3. Ghosted replacement: if currently ghosted and moving to interview/offer/accepted/rejected/withdrawn,
         delete the ghosted record first (it was a pessimistic default, not a real state).
         Exception: 'withdrawn' is blocked when ghosted reflects real silence
         after interviews/an offer (see _has_engagement) — you can only
         withdraw from applied, interview N, or offer.
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

    # 'withdrawn' is a candidate-initiated quit: selectable from applied,
    # interview N, or offer — never from ghosted silence after engagement.
    # (Ghosted with no engagement yet is just the pessimistic default behind
    # applied; withdrawing there is allowed and swaps it out below.)
    if validated == "withdrawn" and current == "ghosted" and _has_engagement(history):
        raise ValueError(
            "Cannot move to 'withdrawn' from 'ghosted' — ghosted means employer "
            "silence, not an active process. Withdraw from applied, interview, or offer."
        )

    # Rule 2 — Draft activation: "draft" is pre-application prep, so every
    # application must pass through "applied" before any outcome. Moving from
    # draft to any real status auto-activates: insert applied, then the normal
    # pessimistic ghosted default (which the ghosted-replacement rule below
    # swaps out when the target is a concrete outcome like interview/rejection).
    if current == "draft":
        db.insert_status(application_id, "applied")
        db.insert_status(application_id, "ghosted")
        logger.info(
            "Application #%d: activated from draft → applied → ghosted", application_id,
        )
        if validated in ("applied", "ghosted"):
            return
        # Target is a post-apply outcome — fall through so the ghosted-
        # replacement rule swaps the transient ghosted for the real status.
        current = "ghosted"
        history = db.get_status_history_with_ids(application_id)

    # Rule 3 — ghosted replacement: pessimistic default was wrong.
    # Ghosted gets replaced by any real outcome (interview, offer, accepted, rejected, withdrawn).
    # Note: withdrawn-from-real-ghosted is already rejected by the guard above,
    # so reaching here with withdrawn means the transient default — swap it out.
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


def _clean_role_stem(role: str) -> str:
    """JD-file stem for a role — mirrors the naming in track()."""
    return re.sub(r'[^\w\-]', '_', role.lower()).strip('_')


def edit_application(
    application_id: int,
    company: str = None,
    role: str = None,
    job_url: str = None,
) -> dict:
    """Corrects company/role/job_url on an application, keeping DB + filesystem in sync.

    Company and role feed the application directory ({company}_{role}_{id})
    and the role-derived JD/CV/cover-letter filenames, so changing them moves
    the directory, renames those files, and repoints the stored paths.
    `None` leaves a field unchanged; `""` clears the job URL.
    """
    db.init_db()

    app = db.get_application(application_id)
    if app is None:
        raise ValueError(f"Application #{application_id} not found.")

    _id, old_company, old_role, jd_path, cv_path, old_url, _created, source, cl_path = app

    new_company = html.unescape(company).strip() if company is not None else old_company
    new_role = html.unescape(role).strip() if role is not None else old_role
    if not new_company:
        raise ValueError("Company must not be empty.")
    if not new_role:
        raise ValueError("Role must not be empty.")
    new_url = job_url.strip() or None if job_url is not None else old_url

    renamed = (new_company, new_role) != (old_company, old_role)
    if renamed:
        clash = db.find_application(new_company, new_role, source=source)
        if clash is not None and clash["id"] != application_id:
            raise ValueError(
                f"Application already tracked — #{clash['id']}: {clash['company']} — {clash['role']}"
            )

    new_jd_path, new_cv_path, new_cl_path = jd_path, cv_path, cl_path

    if renamed:
        old_dir = _build_app_dir(application_id, old_company, old_role)
        new_dir = _build_app_dir(application_id, new_company, new_role)
        if old_dir != new_dir:
            if old_dir.exists():
                if new_dir.exists():
                    raise ValueError(f"Cannot rename: {new_dir} already exists.")
                old_dir.rename(new_dir)
                logger.info("Renamed directory: %s → %s", old_dir, new_dir)
            else:
                new_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Old directory %s missing; created %s", old_dir, new_dir)

        role_changed = new_role != old_role

        # JD file: stem is exactly the cleaned role (see track()).
        if jd_path:
            old_jd = new_dir / Path(jd_path).name
            new_jd = new_dir / f"{_clean_role_stem(new_role)}{Path(jd_path).suffix}"
            if role_changed and old_jd != new_jd and old_jd.exists():
                old_jd.rename(new_jd)
                logger.info("Renamed JD: %s → %s", old_jd, new_jd)
            new_jd_path = str(new_jd if role_changed else old_jd)

        # CV + cover letter: base is cleaned "{candidate} {role}".
        if role_changed:
            try:
                with open(settings.master_cv_path, "r", encoding="utf-8") as f:
                    master_name = json.load(f).get("personal_info", {}).get("name", "Candidate")
                old_base = _build_cv_filename(master_name, old_role)
                new_base = _build_cv_filename(master_name, new_role)
            except (OSError, ValueError):
                old_base = new_base = None
            if old_base and new_base and old_base != new_base:
                for old_name, new_name in (
                    (f"{old_base}.md", f"{new_base}.md"),
                    (f"{old_base}.pdf", f"{new_base}.pdf"),
                    (f"{old_base}_Cover_Letter.md", f"{new_base}_Cover_Letter.md"),
                    (f"{old_base}_Cover_Letter.pdf", f"{new_base}_Cover_Letter.pdf"),
                ):
                    src = new_dir / old_name
                    if src.exists():
                        src.rename(new_dir / new_name)
                        logger.info("Renamed file: %s → %s", src, new_dir / new_name)
                if cv_path:
                    new_cv_path = str(new_dir / f"{new_base}.pdf")
                if cl_path:
                    new_cl_path = str(new_dir / f"{new_base}_Cover_Letter.pdf")
            else:
                if cv_path:
                    new_cv_path = str(new_dir / Path(cv_path).name)
                if cl_path:
                    new_cl_path = str(new_dir / Path(cl_path).name)
        else:
            if cv_path:
                new_cv_path = str(new_dir / Path(cv_path).name)
            if cl_path:
                new_cl_path = str(new_dir / Path(cl_path).name)

        db.update_application(
            application_id,
            jd_path=new_jd_path,
            cv_path=new_cv_path,
            cover_letter_path=new_cl_path,
            company=new_company,
            role=new_role,
        )
        logger.info("Application #%d renamed: %s — %s", application_id, new_company, new_role)

    if job_url is not None and new_url != old_url:
        db.set_application_job_url(application_id, new_url)

    return {
        "id": application_id,
        "company": new_company,
        "role": new_role,
        "job_url": new_url,
        "jd_path": new_jd_path,
        "cv_path": new_cv_path,
        "cover_letter_path": new_cl_path,
    }


def list_all() -> list[tuple]:
    """Returns all applications for display."""
    db.init_db()
    return db.list_applications()
