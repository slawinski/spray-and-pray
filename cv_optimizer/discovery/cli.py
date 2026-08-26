"""Standalone discovery CLI — runs without FastAPI or the TUI."""

import argparse
import json
import logging
import sys
from cv_optimizer.discovery.config import load_config
from cv_optimizer.discovery.lock import DiscoveryLock
from cv_optimizer.discovery.service import DiscoveryService

logger = logging.getLogger(__name__)

LOCK_MESSAGE = "Discovery already in progress."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv-opt discover",
        description="Discover, score, and import frontend job postings.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Fetch/normalize/dedupe/prefilter only — no LLM scoring, no imports.",
    )
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Score and persist, but do not create application Drafts.",
    )
    parser.add_argument(
        "--max-scores",
        type=int,
        default=None,
        help="Override the per-run LLM scoring budget.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        choices=["serpapi", "lever", "ashby", "greenhouse"],
        help="Restrict to one source (repeatable).",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Ignore the job match score cache and produce fresh assessments.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to job_search.json (default: ./job_search.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the run result as JSON on stdout.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Debug logging."
    )
    return parser


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def run_discovery(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)

    try:
        config = load_config(args.config)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    lock = DiscoveryLock()
    if not lock.acquire():
        print(LOCK_MESSAGE)
        return 0
    try:
        service = DiscoveryService(config=config, progress=logger.info)
        result = service.run(
            sources=args.source,
            import_matches=not args.no_import,
            preview=args.preview,
            force_rescore=args.rescore,
            max_scores=args.max_scores,
        )
    finally:
        lock.release()

    if args.json:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        _print_summary(result)

    if result.status == "failed":
        return 1
    return 0


def _print_summary(result) -> None:
    print()
    print(f"Discovery run #{result.run_id} — {result.status}")
    print(f"  fetched:    {result.fetched}")
    print(f"  new:        {result.new}")
    print(f"  updated:    {result.updated}")
    print(f"  filtered:   {result.filtered}")
    print(f"  scored:     {result.scored}")
    print(f"  qualified:  {result.qualified}")
    print(f"  imported:   {result.imported}")
    if result.linked_existing:
        print(f"  linked to existing applications: {result.linked_existing}")
    if result.imported_applications:
        print("  imported Drafts:")
        for entry in result.imported_applications:
            print(
                f"    {entry.get('score')}  {entry.get('company')} — "
                f"{entry.get('role')}  [#{entry.get('application_id')}]"
            )
    if result.errors:
        print(f"  errors:     {len(result.errors)}")
        for error in result.errors[:10]:
            print(f"    - {error}")


if __name__ == "__main__":
    sys.exit(run_discovery())
