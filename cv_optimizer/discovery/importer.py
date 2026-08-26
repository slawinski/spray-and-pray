"""Transactional Draft importer for qualifying discovered jobs.

Creates an Application with status ``draft``, its directory, JD file,
copied Match Assessment, and the job_posting → application link — without
generating a CV or cover letter and without another LLM call.

The DB transaction and the filesystem must never disagree: on failure the
DB work is rolled back and any newly created directory is removed, leaving
the posting retryable.
"""

import logging
import shutil
from pathlib import Path

from cv_optimizer import db
from cv_optimizer.discovery.config import DiscoveryConfig
from cv_optimizer.discovery.dedupe import (
    descriptions_match,
    normalize_url,
)
from cv_optimizer.matching import jd_hash
from cv_optimizer.tracker import _build_app_dir

logger = logging.getLogger(__name__)

# Separator between the metadata header and the canonical JD body in the
# stored JD file. The matcher hashes the whole file, so this must be stable.
JD_META_SEPARATOR = "---"


def build_jd_file_content(job: dict) -> str:
    """Renders the stored JD markdown file (metadata header + canonical JD)."""
    lines = [
        f"# {job['role']}",
        "",
        f"Company: {job['company']}",
    ]
    for label, value in (
        ("Source", _source_label(job)),
        ("URL", job.get("canonical_url")),
        ("Location", job.get("location_text")),
        ("Posted", job.get("posted_at")),
        ("Discovered", job.get("first_seen_at")),
    ):
        if value:
            lines.append(f"{label}: {value}")
    lines += ["", JD_META_SEPARATOR, "", (job.get("description") or "")]
    return "\n".join(lines) + "\n"


def _source_label(job: dict) -> str:
    refs = db.get_job_source_refs(job["id"])
    if refs:
        return ", ".join(sorted({r["source"] for r in refs}))
    return "discovery"


def _jd_body_from_file(path: Path) -> str:
    """Returns the JD portion of a stored JD file (after the separator)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if JD_META_SEPARATOR in text:
        return text.split(JD_META_SEPARATOR, 1)[1].strip()
    return text.strip()


class ImportError_(Exception):
    """A discovered job could not be imported as a Draft."""


class DraftImporter:
    """Imports qualifying job postings as Draft applications.

    NEVER calls ``tracker.track()`` — that path continues into CV/cover
    letter generation, which discovery must not trigger by default.
    """

    def __init__(self, config: DiscoveryConfig) -> None:
        self.config = config

    def import_job(self, job_posting_id: int) -> dict:
        """Imports a qualifying posting; returns
        {'application_id': int, 'linked_existing': bool, 'assessment_copied': bool}.
        """
        conn = db.connect()
        app_dir: Path | None = None
        try:
            job = self._reload(conn, job_posting_id)

            # Preconditions.
            if job["user_state"] == "dismissed":
                raise ImportError_(f"Job posting #{job_posting_id} is dismissed")
            if job["prefilter_state"] == "fail":
                raise ImportError_(f"Job posting #{job_posting_id} failed prefilter")
            if job["active_state"] == "inactive":
                raise ImportError_(f"Job posting #{job_posting_id} is inactive")
            if job["application_id"] is not None:
                return {
                    "application_id": job["application_id"],
                    "linked_existing": False,
                    "assessment_copied": False,
                    "already_imported": True,
                }

            assessment = self._latest_assessment(conn, job_posting_id)
            if assessment is None:
                raise ImportError_(
                    f"Job posting #{job_posting_id} has no match assessment"
                )
            if assessment["score"] < self.config.minimum_match_score:
                raise ImportError_(
                    f"Job posting #{job_posting_id} scored "
                    f"{assessment['score']} < {self.config.minimum_match_score}"
                )

            # Existing manual application dedupe.
            existing_app_id = self._find_existing_application(job)
            if existing_app_id is not None:
                self._link(conn, job_posting_id, existing_app_id)
                copied = self._copy_assessment_if_absent(
                    conn, existing_app_id, assessment
                )
                conn.commit()
                logger.info(
                    "Job posting #%s linked to existing application #%s",
                    job_posting_id, existing_app_id,
                )
                return {
                    "application_id": existing_app_id,
                    "linked_existing": True,
                    "assessment_copied": copied,
                    "already_imported": False,
                }

            # Create the application row (jd_path set after the file exists).
            cursor = conn.execute(
                "INSERT INTO applications (company, role, jd_path, cv_path, "
                "job_url, source) VALUES (?, ?, NULL, NULL, ?, ?)",
                (
                    job["company"],
                    job["role"],
                    job["canonical_url"],
                    self._auto_source_label(job),
                ),
            )
            app_id = cursor.lastrowid

            # Filesystem: directory + JD file.
            app_dir = _build_app_dir(app_id, job["company"], job["role"])
            app_dir.mkdir(parents=True, exist_ok=False)
            jd_file = app_dir / "job_description.md"
            jd_file.write_text(build_jd_file_content(job), encoding="utf-8")
            jd_path_str = str(jd_file)

            conn.execute(
                "UPDATE applications SET jd_path = ? WHERE id = ?",
                (jd_path_str, app_id),
            )

            # Initial status: draft (first transition — trigger-safe).
            conn.execute(
                "INSERT INTO status_history (application_id, status) VALUES (?, 'draft')",
                (app_id,),
            )

            # Copy the already-paid-for assessment (no LLM call).
            self._copy_assessment(conn, app_id, assessment)

            # Link posting → application, mark imported.
            conn.execute(
                "UPDATE job_postings SET application_id = ?, user_state = 'imported', "
                "imported_at = CURRENT_TIMESTAMP WHERE id = ?",
                (app_id, job_posting_id),
            )

            conn.commit()
            logger.info(
                "Imported job posting #%s as Draft application #%s",
                job_posting_id, app_id,
            )
            return {
                "application_id": app_id,
                "linked_existing": False,
                "assessment_copied": True,
                "already_imported": False,
            }
        except Exception:
            conn.rollback()
            if app_dir is not None and app_dir.exists():
                shutil.rmtree(app_dir, ignore_errors=True)
                logger.warning("Removed incomplete application dir %s", app_dir)
            raise
        finally:
            conn.close()

    # ── Internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _reload(conn, job_posting_id: int) -> dict:
        conn.row_factory = None
        row = conn.execute(
            "SELECT * FROM job_postings WHERE id = ?", (job_posting_id,)
        ).fetchone()
        if row is None:
            raise ImportError_(f"Job posting #{job_posting_id} not found")
        columns = [c[0] for c in conn.execute(
            "SELECT * FROM job_postings LIMIT 0"
        ).description]
        return dict(zip(columns, row))

    @staticmethod
    def _latest_assessment(conn, job_posting_id: int) -> dict | None:
        row = conn.execute(
            "SELECT * FROM job_match_assessments WHERE job_posting_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (job_posting_id,),
        ).fetchone()
        if row is None:
            return None
        columns = [c[0] for c in conn.execute(
            "SELECT * FROM job_match_assessments LIMIT 0"
        ).description]
        return dict(zip(columns, row))

    def _auto_source_label(self, job: dict) -> str:
        refs = db.get_job_source_refs(job["id"])
        primary = refs[0]["source"] if refs else "discovery"
        return f"auto:{primary}"

    def _find_existing_application(self, job: dict) -> int | None:
        """Finds an equivalent manual application: normalized URL, then
        company + role + equivalent JD. Returns its id or None."""
        canonical = normalize_url(job.get("canonical_url"))
        refs = db.get_job_source_refs(job["id"])
        ref_urls = {
            normalized
            for ref in refs
            for candidate in (ref.get("source_url"), ref.get("apply_url"))
            if (normalized := normalize_url(candidate))
        }
        all_urls = ref_urls | ({canonical} if canonical else set())

        candidates = db.list_applications_with_status()
        # Priority 1: normalized job URL.
        for app in candidates:
            app_url = normalize_url(app.get("job_url"))
            if app_url and app_url in all_urls:
                return app["id"]

        # Priority 2: company + role + equivalent JD.
        for app in candidates:
            if (
                (app["company"] or "").strip().lower()
                != (job["company"] or "").strip().lower()
                or (app["role"] or "").strip().lower()
                != (job["role"] or "").strip().lower()
            ):
                continue
            jd_path = app.get("jd_path")
            if not jd_path or not Path(jd_path).exists():
                continue
            try:
                existing_jd = _jd_body_from_file(Path(jd_path))
            except OSError:
                continue
            if descriptions_match(existing_jd, job["description"]):
                return app["id"]

        # Priority 3: existing source identity — applications do not store an
        # external id, so this signal is genuinely unavailable. Do NOT link on
        # company+role alone: same-title vacancies at one employer must never
        # be merged (spec §39 "if available", §17.4 preserve two postings).
        return None

    @staticmethod
    def _link(conn, job_posting_id: int, application_id: int) -> None:
        conn.execute(
            "UPDATE job_postings SET application_id = ?, user_state = 'imported', "
            "imported_at = CURRENT_TIMESTAMP WHERE id = ?",
            (application_id, job_posting_id),
        )

    def _effective_jd_hash(self, conn, application_id: int, assessment: dict) -> str:
        """Hash of the application's own stored JD file.

        The stored file includes a metadata header, so its hash differs from
        the canonical description hash. Storing the file-derived hash keeps
        future application-level scoring cache hits consistent with the text
        the application scorer actually hashes.
        """
        row = conn.execute(
            "SELECT jd_path FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if row and row[0] and Path(row[0]).exists():
            try:
                return jd_hash(Path(row[0]).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        return assessment["jd_hash"]

    def _copy_assessment_if_absent(
        self, conn, application_id: int, assessment: dict
    ) -> bool:
        """Copies the job assessment to the application unless an identical
        identity already exists there."""
        effective_jd_hash = self._effective_jd_hash(conn, application_id, assessment)
        existing = conn.execute(
            "SELECT id FROM match_assessments WHERE application_id = ? "
            "AND candidate_hash = ? AND jd_hash = ? AND scoring_version = ? "
            "AND prompt_version = ? AND model_name = ? LIMIT 1",
            (
                application_id,
                assessment["candidate_hash"],
                effective_jd_hash,
                assessment["scoring_version"],
                assessment["prompt_version"],
                assessment["model_name"],
            ),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO match_assessments "
            "(application_id, score, label, confidence, base_score, assessment_json, "
            " candidate_hash, jd_hash, scoring_version, prompt_version, model_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                application_id,
                assessment["score"],
                assessment["label"],
                assessment["confidence"],
                assessment["base_score"],
                assessment["assessment_json"],
                assessment["candidate_hash"],
                effective_jd_hash,
                assessment["scoring_version"],
                assessment["prompt_version"],
                assessment["model_name"],
            ),
        )
        return True

    def _copy_assessment(
        self, conn, application_id: int, assessment: dict
    ) -> None:
        """Copies the job assessment into application match persistence.

        The stored jd_hash reflects the stored JD file (metadata header +
        canonical JD) so future application-level scoring hits this cache
        instead of paying for a second LLM call.
        """
        effective_jd_hash = self._effective_jd_hash(conn, application_id, assessment)
        conn.execute(
            "INSERT INTO match_assessments "
            "(application_id, score, label, confidence, base_score, assessment_json, "
            " candidate_hash, jd_hash, scoring_version, prompt_version, model_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                application_id,
                assessment["score"],
                assessment["label"],
                assessment["confidence"],
                assessment["base_score"],
                assessment["assessment_json"],
                assessment["candidate_hash"],
                effective_jd_hash,
                assessment["scoring_version"],
                assessment["prompt_version"],
                assessment["model_name"],
            ),
        )
