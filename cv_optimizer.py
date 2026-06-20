import json
import logging
import argparse
import sys
from typing import Optional

from cv_optimizer.config import settings
from cv_optimizer.extractor import PDFExtractor
from cv_optimizer.optimizer import CVOptimizer
from cv_optimizer.generator import PDFGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def cmd_optimize(args):
    """Original CV optimization flow."""
    try:
        # If app_id is provided, override the output paths and job description from the tracker.
        if getattr(args, 'app_id', None) is not None:
            from cv_optimizer import db
            from cv_optimizer.tracker import _build_app_dir, _build_cv_filename
            db.init_db()
            app = db.get_application(args.app_id)
            if app is None:
                logger.error(f"Application #{args.app_id} not found.")
                sys.exit(1)
            
            company, role, jd_path = app[1], app[2], app[3]
            
            # Use the tracked JD path if no job-offer is provided, else keep user's choice
            if args.job_offer == settings.job_description_path and jd_path:
                args.job_offer = jd_path

            logger.info(f"Loading Master CV from {args.master_cv}...")
            with open(args.master_cv, "r", encoding="utf-8") as f:
                master_cv_data = json.load(f)

            app_dir = _build_app_dir(args.app_id, company, role)
            candidate_name = master_cv_data.get("personal_info", {}).get("name", "Candidate")
            cv_base_name = _build_cv_filename(candidate_name, role)

            args.output_md = str(app_dir / f"{cv_base_name}.md")
            args.output_pdf = str(app_dir / f"{cv_base_name}.pdf")
            
            # Make sure directory exists if it was deleted
            app_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using application directory: {app_dir}")
        else:
            logger.info(f"Loading Master CV from {args.master_cv}...")
            with open(args.master_cv, "r", encoding="utf-8") as f:
                master_cv_data = json.load(f)

        logger.info(f"Extracting job description from {args.job_offer}...")
        job_description = PDFExtractor.extract_text(args.job_offer)

        optimizer = CVOptimizer(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model_name=settings.model_name,
            temperature=settings.temperature,
            num_ctx=settings.num_ctx
        )
        optimized_cv_md = optimizer.optimize(master_cv_data, job_description)

        logger.info(f"Saving optimized CV to {args.output_md}...")
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(optimized_cv_md)

        generator = PDFGenerator()
        generator.generate(optimized_cv_md, args.output_pdf)

        if getattr(args, 'app_id', None) is not None:
            from cv_optimizer import db
            db.init_db()
            db.update_application(args.app_id, cv_path=args.output_pdf)

        logger.info("Success! Optimization complete.")

    except FileNotFoundError as e:
        logger.error(f"File not found: {e.filename}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from {args.master_cv}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def cmd_track(args):
    """Initializes a new application in the DB."""
    from cv_optimizer.tracker import track
    try:
        app_id = track(args.company, args.role, args.jd, args.master_cv)
        print(f"✓ Application #{app_id} tracked: {args.company} — {args.role}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to track application: {e}")
        sys.exit(1)


def cmd_status(args):
    """Appends a new status to an existing application."""
    from cv_optimizer.tracker import update_status
    try:
        update_status(args.id, args.status)
        print(f"✓ Application #{args.id}: → {args.status}")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        sys.exit(1)


def cmd_sankey(args):
    """Generates and prints the Sankey funnel diagram."""
    from cv_optimizer.sankey import generate_sankey
    try:
        output = generate_sankey()
        print(output)
    except Exception as e:
        logger.error(f"Failed to generate Sankey: {e}")
        sys.exit(1)


def cmd_list(args):
    """Lists all tracked applications."""
    from cv_optimizer.tracker import list_all
    try:
        apps = list_all()
        if not apps:
            print("No applications tracked yet.")
            return

        print(f"\n{'ID':>4}  {'Company':<20}  {'Role':<30}  {'Created'}")
        print("─" * 80)
        for app in apps:
            app_id, company, role, jd_path, cv_path, created_at = app
            print(f"{app_id:>4}  {company:<20}  {role:<30}  {created_at}")
        print(f"\nTotal: {len(apps)} applications\n")
    except Exception as e:
        logger.error(f"Failed to list applications: {e}")
        sys.exit(1)


def main():
    """
    Main entry point for the CV Optimizer CLI.
    """
    parser = argparse.ArgumentParser(
        prog="cv-opt",
        description="Optimize your CV for a specific job description using local LLMs."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- optimize (default behavior) ---
    opt_parser = subparsers.add_parser("optimize", help="Generate an optimized CV")
    opt_parser.add_argument(
        "--master-cv",
        default=settings.master_cv_path,
        help=f"Path to master CV JSON (default: {settings.master_cv_path})"
    )
    opt_parser.add_argument(
        "--job-offer",
        default=settings.job_description_path,
        help=f"Path to job offer PDF (default: {settings.job_description_path})"
    )
    opt_parser.add_argument(
        "--app-id",
        type=int,
        help="Optional. Re-optimize for an existing application ID. If provided, overrides output paths to save directly in the application folder."
    )
    opt_parser.add_argument(
        "--output-md",
        default=settings.output_md_path,
        help=f"Path to save optimized markdown (default: {settings.output_md_path})"
    )
    opt_parser.add_argument(
        "--output-pdf",
        default=settings.output_pdf_path,
        help=f"Path to save optimized PDF (default: {settings.output_pdf_path})"
    )
    opt_parser.set_defaults(func=cmd_optimize)

    # --- track ---
    track_parser = subparsers.add_parser(
        "track", help="Track a new job application"
    )
    track_parser.add_argument("company", help="Company name")
    track_parser.add_argument("role", help="Job role/title")
    track_parser.add_argument(
        "--jd", required=True,
        help="Path to the Job Description file (PDF or TXT)"
    )
    track_parser.add_argument(
        "--master-cv",
        default=settings.master_cv_path,
        help=f"Path to master CV JSON (default: {settings.master_cv_path})"
    )
    track_parser.set_defaults(func=cmd_track)

    # --- status ---
    status_parser = subparsers.add_parser(
        "status", help="Update application status"
    )
    status_parser.add_argument("id", type=int, help="Application ID")
    status_parser.add_argument(
        "status",
        help="New status (applied, ghosted, rejected, interview N, offer, accepted)"
    )
    status_parser.set_defaults(func=cmd_status)

    # --- sankey ---
    sankey_parser = subparsers.add_parser(
        "sankey", help="Generate application funnel Sankey diagram"
    )
    sankey_parser.set_defaults(func=cmd_sankey)

    # --- list ---
    list_parser = subparsers.add_parser(
        "list", help="List all tracked applications"
    )
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)

if __name__ == "__main__":
    main()
