"""Sankey-style funnel diagram from application tracking transitions."""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def build_sankey_flows(
    transitions: list[tuple[int, str, str]],
) -> dict[tuple[str, str], int]:
    """Build aggregated (from_status, to_status) -> weight mapping.

    Args:
        transitions: Pre-sorted list of (application_id, status, transitioned_at).

    Returns:
        Dict mapping each unique (source, target) pair to its occurrence count.
    """
    # Group transitions by application_id, preserving order.
    apps: dict[int, list[str]] = defaultdict(list)
    for app_id, status, _ in transitions:
        apps[app_id].append(status)

    flows: dict[tuple[str, str], int] = defaultdict(int)

    for app_id, chain in apps.items():
        cleaned = _clean_ghosted(chain)
        logger.debug("app %d chain %s -> %s", app_id, chain, cleaned)
        for i in range(len(cleaned) - 1):
            flows[(cleaned[i], cleaned[i + 1])] += 1

    return dict(flows)


def _clean_ghosted(chain: list[str]) -> list[str]:
    """Remove ghosted entries when a non-ghosted status follows the first ghosted.

    Rules:
      - If ghosted is terminal (nothing non-ghosted after first ghosted): keep it.
      - If any non-ghosted status appears after the first ghosted: strip ALL ghosted.
    """
    try:
        first_ghosted_idx = chain.index("ghosted")
    except ValueError:
        return chain  # no ghosted at all

    has_non_ghosted_after = any(
        s != "ghosted" for s in chain[first_ghosted_idx + 1 :]
    )

    if has_non_ghosted_after:
        return [s for s in chain if s != "ghosted"]

    return chain


def render_sankey(flows: dict[tuple[str, str], int]) -> str:
    """Render flows as an ASCII Sankey table for the terminal.

    Sorted by source alphabetically, then weight descending.
    """
    if not flows:
        return "No transitions to display."

    sorted_flows = sorted(flows.items(), key=lambda item: (item[0][0], -item[1]))

    max_source_len = max(len(src) for (src, _), _ in sorted_flows)
    total = sum(
        weight
        for (src, _), weight in sorted_flows
        if src == sorted_flows[0][0][0] or True  # sum all weights
    )
    # Total applications = unique source entries at the root level isn't meaningful;
    # use the sum of weights from root-level sources (those that never appear as targets).
    all_targets = {tgt for (_, tgt), _ in sorted_flows}
    all_sources = {src for (src, _), _ in sorted_flows}
    root_sources = all_sources - all_targets
    total_apps = sum(
        weight for (src, _), weight in sorted_flows if src in root_sources
    )

    lines: list[str] = []
    header = "Application Funnel (Sankey)"
    separator = "═" * 38

    lines.append(header)
    lines.append(separator)

    for (src, tgt), weight in sorted_flows:
        padded_src = src.ljust(max_source_len)
        lines.append(f"{padded_src} ──[ {weight} ]──▶  {tgt}")

    lines.append(separator)
    lines.append(f"Total applications: {total_apps}")

    return "\n".join(lines)


def generate_sankey() -> str:
    """Convenience entry point: fetch transitions from DB, build & render."""
    from cv_optimizer import db

    transitions = db.get_all_transitions()
    logger.info("Loaded %d raw transitions", len(transitions))

    flows = build_sankey_flows(transitions)
    return render_sankey(flows)
