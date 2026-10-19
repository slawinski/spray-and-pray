"""Checked-document publication with caught-failure recovery (not crash atomicity)."""

import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Literal

from cv_optimizer import db
from cv_optimizer.profiles import validate_profile_name


def publish_document(
    app_id: int,
    profile: str,
    revision: int,
    markdown: str,
    pdf_path: str | Path,
    renderer: Callable[[str, str], None],
    document_type: Literal["cv", "cover_letter"],
) -> str:
    """Publish already-checked Markdown/PDF and return the stored PDF path.

    The caller must check this exact Markdown against the captured profile.
    Rendering occurs outside the write lock; promotion and path persistence share
    a short BEGIN IMMEDIATE transaction with selection changes. Failures raise,
    restoring replaced files and retaining the prior database path.
    """
    column = {"cv": "cv_path", "cover_letter": "cover_letter_path"}.get(document_type)
    if column is None:
        raise ValueError("document_type must be 'cv' or 'cover_letter'")
    validate_profile_name(profile)
    pdf_path = Path(pdf_path)
    md_path = pdf_path.with_suffix(".md")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{pdf_path.stem}-", dir=pdf_path.parent) as temporary:
        stage = Path(temporary)
        staged_md, staged_pdf = stage / md_path.name, stage / pdf_path.name
        staged_md.write_text(markdown, encoding="utf-8")
        renderer(markdown, str(staged_pdf))
        conn = db.connect()
        replaced = []
        backups = {}
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT cv_profile, cv_profile_revision FROM applications WHERE id = ?",
                (app_id,),
            ).fetchone()
            if current != (profile, revision):
                raise ValueError("Application profile/revision changed; generate the document again")
            for destination in (md_path, pdf_path):
                if destination.exists():
                    backup = stage / (destination.name + ".backup")
                    shutil.copy2(destination, backup)
                    backups[destination] = backup
            for staged, destination in ((staged_md, md_path), (staged_pdf, pdf_path)):
                staged.replace(destination)
                replaced.append(destination)
            # Column comes only from the closed document-type mapping above.
            conn.execute(f"UPDATE applications SET {column} = ? WHERE id = ?",
                         (str(pdf_path), app_id))
            conn.commit()
        except Exception:
            try:
                for destination in reversed(replaced):
                    if destination in backups:
                        os.replace(backups[destination], destination)
                    else:
                        destination.unlink()
            finally:
                conn.rollback()
            raise
        finally:
            conn.close()
    return str(pdf_path)
