"""Sankey-style funnel diagram from application tracking transitions."""

import logging
import tempfile
import webbrowser
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def build_sankey_flows(
    transitions: list[tuple[int, str, str]],
) -> dict[tuple[str, str], int]:
    """Build aggregated (from_status, to_status) -> weight mapping.

    Args:
        transitions: Pre-sorted list of (application_id, status, transitioned_at).

    Returns:
        Dict mapping each unique (source, target) pair to its occurrence count.

    "draft" is stripped up front: it represents pre-application prep rather
    than a real funnel stage, so the diagram starts at "applied" and
    still-draft applications contribute no edges.
    """
    # Group transitions by application_id, preserving order.
    apps: dict[int, list[str]] = defaultdict(list)
    for app_id, status, _ in transitions:
        apps[app_id].append(status)

    flows: dict[tuple[str, str], int] = defaultdict(int)

    for app_id, chain in apps.items():
        active = _strip_draft(chain)
        cleaned = _clean_ghosted(active)
        deduped = _deduplicate_consecutive(cleaned)
        logger.debug("app %d chain %s -> %s -> %s", app_id, chain, cleaned, deduped)
        for i in range(len(deduped) - 1):
            flows[(deduped[i], deduped[i + 1])] += 1

    return dict(flows)


def _strip_draft(chain: list[str]) -> list[str]:
    """Drop 'draft' entries — pre-application prep isn't part of the funnel.

    Applications that never leave draft produce no edges and are thus
    excluded from the Sankey entirely.
    """
    return [s for s in chain if s != "draft"]


def _clean_ghosted(chain: list[str]) -> list[str]:
    """Strip ghosted entries that are transient (followed by a non-ghosted status).

    A ghosted entry represents employer silence. If the employer eventually
    responds (interview, offer, rejection), that ghosted period was a transient
    waiting state and should not clutter the funnel.

    Rules (per entry, NOT first-ghosted-triggers-all):
      - Ghosted followed by a non-ghosted → strip (it was transient).
      - Ghosted terminal / only followed by more ghosted → keep (it's the resolution).
    """
    if not chain:
        return chain

    result: list[str] = []
    for i, status in enumerate(chain):
        if status != "ghosted":
            result.append(status)
            continue

        # Check what comes after this ghosted entry
        after = chain[i + 1 :]
        has_non_ghosted_after = any(s != "ghosted" for s in after)
        if has_non_ghosted_after:
            continue  # transient ghosted — skip it
        else:
            result.append(status)  # terminal ghosted — keep it

    return result


def _deduplicate_consecutive(chain: list[str]) -> list[str]:
    """Collapse consecutive identical statuses into single occurrences.

    Prevents self-loops in the Sankey diagram caused by back-and-forth
    toggling between statuses (e.g. applied → ghosted → applied → ghosted
    produces ["applied", "applied"] after ghosted cleaning).
    """
    if not chain:
        return chain
    result: list[str] = [chain[0]]
    for status in chain[1:]:
        if status != result[-1]:
            result.append(status)
    return result


def _node_counts(flows: dict[tuple[str, str], int]) -> dict[str, int]:
    """Compute per-status application counts from flow data.

    Each node's count is max(incoming, outgoing) — the number of applications
    that passed through that status.
    """
    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    for (src, tgt), weight in flows.items():
        outgoing[src] += weight
        incoming[tgt] += weight

    all_nodes = set(incoming) | set(outgoing)
    counts: dict[str, int] = {}
    for node in all_nodes:
        counts[node] = max(incoming.get(node, 0), outgoing.get(node, 0))
    return counts


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

    # Per-status application counts (node values), sorted canonically
    node_counts = _node_counts(flows)
    sorted_counts = sorted(node_counts.items(), key=lambda kv: (
        -1 if kv[0] == "draft" else
        0 if kv[0] == "applied" else
        1 if kv[0].startswith("interview") else
        2 if kv[0] == "offer" else
        3 if kv[0] == "accepted" else
        4 if kv[0] == "rejected" else 5,
        kv[0],
    ))
    count_parts = ", ".join(f"{s}: {c}" for s, c in sorted_counts)
    lines.append(separator)
    lines.append(f"Total applications: {total_apps}")
    lines.append(count_parts)

    return "\n".join(lines)


def generate_sankey() -> str:
    """Convenience entry point: fetch transitions from DB, build & render."""
    from cv_optimizer import db

    transitions = db.get_all_transitions()
    logger.info("Loaded %d raw transitions", len(transitions))

    flows = build_sankey_flows(transitions)
    return render_sankey(flows)


STATUS_COLORS_SANKEY = {
    "draft": "rgba(255, 235, 59, 0.7)",
    "applied": "rgba(0, 188, 212, 0.8)",
    "interview 1": "rgba(76, 175, 80, 0.8)",
    "interview 2": "rgba(139, 195, 74, 0.8)",
    "interview 3": "rgba(205, 220, 57, 0.8)",
    "offer": "rgba(255, 193, 7, 0.8)",
    "accepted": "rgba(0, 200, 83, 0.9)",
    "rejected": "rgba(244, 67, 54, 0.8)",
    "ghosted": "rgba(158, 158, 158, 0.6)",
}


def _node_color(status: str) -> str:
    base = status.rsplit(None, 1)[0] if "interview" in status else status
    return STATUS_COLORS_SANKEY.get(status, STATUS_COLORS_SANKEY.get(base, "rgba(100, 100, 100, 0.8)"))


def generate_sankey_html() -> Path:
    """Generate a Plotly Sankey HTML file and open it in the browser."""
    from cv_optimizer import db

    transitions = db.get_all_transitions()
    flows = build_sankey_flows(transitions)

    nodes_set: set[str] = set()
    for src, tgt in flows:
        nodes_set.add(src)
        nodes_set.add(tgt)
    nodes = sorted(nodes_set, key=lambda s: (
        -1 if s == "draft" else
        0 if s == "applied" else
        1 if s.startswith("interview") else
        2 if s == "offer" else
        3 if s == "accepted" else
        4 if s == "rejected" else 5,
        s,
    ))
    node_index = {n: i for i, n in enumerate(nodes)}

    node_counts = _node_counts(flows)
    labels_json = str([f"{n} ({node_counts.get(n, 0)})" for n in nodes])
    colors_json = str([_node_color(n) for n in nodes])
    source = []
    target = []
    value = []
    for (src, tgt), weight in flows.items():
        source.append(node_index[src])
        target.append(node_index[tgt])
        value.append(weight)

    source_json = str(source)
    target_json = str(target)
    value_json = str(value)

    total_apps = sum(
        weight for (src, _), weight in flows.items()
        if src == "applied"
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Application Funnel — Sankey</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body {{ margin: 0; background: #1e1e2e; display: flex; justify-content: center; align-items: center; height: 100vh; }}
  #sankey {{ width: 900px; height: 600px; }}
</style>
</head>
<body>
<div id="sankey"></div>
<script>
  var data = [{{
    type: "sankey",
    orientation: "h",
    node: {{
      pad: 20,
      thickness: 20,
      line: {{ color: "rgba(255,255,255,0.2)", width: 1 }},
      label: {labels_json},
      color: {colors_json},
    }},
    link: {{
      source: {source_json},
      target: {target_json},
      value: {value_json},
      color: "rgba(255,255,255,0.15)",
    }}
  }}];
  var layout = {{
    title: {{
      text: "Application Funnel — {total_apps} total applications",
      font: {{ color: "#cdd6f4", size: 18 }},
    }},
    font: {{ color: "#cdd6f4", size: 13 }},
    paper_bgcolor: "#1e1e2e",
    plot_bgcolor: "#1e1e2e",
    margin: {{ l: 20, r: 20, t: 50, b: 20 }},
  }};
  Plotly.newPlot("sankey", data, layout, {{ responsive: true }});
</script>
</body>
</html>"""

    out = Path(tempfile.mkdtemp()) / "sankey.html"
    out.write_text(html)
    webbrowser.open(f"file://{out.resolve()}")
    logger.info("Opened Sankey diagram at %s", out)
    return out
