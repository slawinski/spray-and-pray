"""Tests for the Sankey ghosted-exclusion logic and rendering."""
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_optimizer.sankey import build_sankey_flows, _clean_ghosted, _deduplicate_consecutive, _strip_draft, render_sankey


def test_ghosted_cleaning_idempotent():
    """Per-entry ghosted cleaning: transient ghosted stripped, terminal ghosted kept."""
    chain = ["applied", "ghosted", "applied", "ghosted"]
    cleaned = _clean_ghosted(chain)
    # First ghosted is transient (followed by "applied") → stripped.
    # Last ghosted is terminal → kept.
    assert cleaned == ["applied", "applied", "ghosted"]
    # Deduplication collapses the consecutive "applied"s, leaves terminal ghosted
    assert _deduplicate_consecutive(cleaned) == ["applied", "ghosted"]


def test_deduplicate_consecutive_no_change():
    """No consecutive duplicates → chain unchanged."""
    chain = ["applied", "interview 1", "interview 2", "rejected"]
    assert _deduplicate_consecutive(chain) == chain


def test_deduplicate_consecutive_collapses():
    """Consecutive identical statuses → collapsed."""
    chain = ["applied", "applied", "applied", "ghosted"]
    assert _deduplicate_consecutive(chain) == ["applied", "ghosted"]


def test_deduplicate_consecutive_empty():
    """Empty chain → empty."""
    assert _deduplicate_consecutive([]) == []
    assert _deduplicate_consecutive(["applied"]) == ["applied"]


def test_circular_ghosted_applied_no_self_loop():
    """Back-and-forth toggling should NOT produce a self-loop, but terminal ghosted IS shown."""
    transitions = [
        (1, "applied", "t1"),
        (1, "ghosted", "t2"),
        (1, "applied", "t3"),
        (1, "ghosted", "t4"),
    ]
    flows = build_sankey_flows(transitions)
    # After per-entry cleaning + dedup: ["applied", "ghosted"] → one edge
    assert ("applied", "applied") not in flows
    assert ("ghosted", "applied") not in flows
    assert ("applied", "ghosted") in flows
    assert flows[("applied", "ghosted")] == 1


def test_circular_ghosted_applied_ends_ghosted():
    """Ends with ghosted as terminal: applied → ghosted → applied → ghosted → shows applied→ghosted."""
    transactions = [
        (1, "applied", "t1"),
        (1, "ghosted", "t2"),
        (1, "applied", "t3"),
        (1, "ghosted", "t4"),
    ]
    # Chain: ["applied", "ghosted", "applied", "ghosted"]
    # Per-entry: first ghosted is transient (followed by "applied"), terminal ghosted kept
    # After clean: ["applied", "applied", "ghosted"] → dedup: ["applied", "ghosted"]
    flows = build_sankey_flows(transactions)
    assert ("applied", "applied") not in flows
    assert flows == {("applied", "ghosted"): 1}


def test_ghosted_terminal():
    """ghosted as terminal status → kept."""
    chain = ["applied", "ghosted"]
    assert _clean_ghosted(chain) == ["applied", "ghosted"]


def test_ghosted_with_subsequent():
    """ghosted followed by non-ghosted → ghosted removed."""
    chain = ["applied", "ghosted", "interview 1", "rejected"]
    assert _clean_ghosted(chain) == ["applied", "interview 1", "rejected"]


def test_ghosted_multiple_with_subsequent():
    """Multiple ghosted entries: transient first one stripped, terminal last one kept."""
    chain = ["applied", "ghosted", "interview 1", "ghosted"]
    assert _clean_ghosted(chain) == ["applied", "interview 1", "ghosted"]


def test_no_ghosted():
    """No ghosted at all → chain unchanged."""
    chain = ["applied", "interview 1", "offer", "accepted"]
    assert _clean_ghosted(chain) == ["applied", "interview 1", "offer", "accepted"]


def test_build_flows_spec_example_1():
    """Spec example: applied → ghosted (terminal)."""
    transitions = [(1, "applied", "t1"), (1, "ghosted", "t2")]
    flows = build_sankey_flows(transitions)
    assert flows == {("applied", "ghosted"): 1}


def test_build_flows_spec_example_2():
    """Spec example: applied → ghosted → interview 1 → rejected."""
    transitions = [
        (1, "applied", "t1"),
        (1, "ghosted", "t2"),
        (1, "interview 1", "t3"),
        (1, "rejected", "t4"),
    ]
    flows = build_sankey_flows(transitions)
    assert flows == {
        ("applied", "interview 1"): 1,
        ("interview 1", "rejected"): 1,
    }


def test_build_flows_aggregation():
    """Multiple apps aggregate into weighted transitions."""
    transitions = [
        (1, "applied", "t1"), (1, "ghosted", "t2"),
        (2, "applied", "t1"), (2, "ghosted", "t2"),
        (3, "applied", "t1"), (3, "ghosted", "t2"), (3, "interview 1", "t3"),
    ]
    flows = build_sankey_flows(transitions)
    assert flows[("applied", "ghosted")] == 2
    assert flows[("applied", "interview 1")] == 1


def test_render_sankey_empty():
    """Empty flows → informative message."""
    assert render_sankey({}) == "No transitions to display."


def test_render_sankey_output():
    """Smoke test: render produces non-empty formatted output."""
    flows = {("applied", "ghosted"): 5, ("applied", "interview 1"): 3}
    output = render_sankey(flows)
    assert "Application Funnel" in output
    assert "applied" in output
    assert "ghosted" in output
    assert "──[" in output


def test_strip_draft_removes_all_draft():
    """Draft entries are removed regardless of position."""
    assert _strip_draft(["draft", "applied", "ghosted"]) == ["applied", "ghosted"]
    assert _strip_draft(["draft"]) == []
    assert _strip_draft(["applied", "rejected"]) == ["applied", "rejected"]


def test_draft_only_app_produces_no_flows():
    """An application still in draft contributes no edges to the Sankey."""
    transitions = [(1, "draft", "t1")]
    assert build_sankey_flows(transitions) == {}


def test_draft_leading_chain_starts_at_applied():
    """draft → applied → rejected renders as applied → rejected (no draft node)."""
    transitions = [
        (1, "draft", "t1"),
        (1, "applied", "t2"),
        (1, "rejected", "t3"),
    ]
    flows = build_sankey_flows(transitions)
    assert "draft" not in {s for s, _ in flows} | {t for _, t in flows}
    assert flows == {("applied", "rejected"): 1}


def test_draft_stripped_before_ghosted_cleaning():
    """draft → applied → ghosted → interview 1 → draft is impossible, but if a
    stray draft existed it must not interfere with ghosted cleaning."""
    transitions = [
        (1, "draft", "t1"),
        (1, "applied", "t2"),
        (1, "ghosted", "t3"),
        (1, "interview 1", "t4"),
    ]
    flows = build_sankey_flows(transitions)
    assert "draft" not in {s for s, _ in flows} | {t for _, t in flows}
    assert flows == {("applied", "interview 1"): 1}


def test_circular_ghosted_applied_resolves():
    """Back-and-forth that eventually resolves: applied → ghosted → applied → ghosted → interview 1."""
    transitions = [
        (1, "applied", "t1"),
        (1, "ghosted", "t2"),
        (1, "applied", "t3"),
        (1, "ghosted", "t4"),
        (1, "interview 1", "t5"),
    ]
    flows = build_sankey_flows(transitions)
    # After ghosted cleaning: ["applied", "applied", "interview 1"]
    # After dedup: ["applied", "interview 1"]
    assert flows == {("applied", "interview 1"): 1}
    assert ("applied", "applied") not in flows
    assert ("ghosted", "applied") not in flows


if __name__ == "__main__":
    test_ghosted_terminal()
    test_ghosted_with_subsequent()
    test_ghosted_multiple_with_subsequent()
    test_no_ghosted()
    test_ghosted_cleaning_idempotent()
    test_deduplicate_consecutive_no_change()
    test_deduplicate_consecutive_collapses()
    test_deduplicate_consecutive_empty()
    test_build_flows_spec_example_1()
    test_build_flows_spec_example_2()
    test_build_flows_aggregation()
    test_render_sankey_empty()
    test_render_sankey_output()
    test_circular_ghosted_applied_no_self_loop()
    test_circular_ghosted_applied_ends_ghosted()
    test_circular_ghosted_applied_resolves()
    print("✓ All 16 tests passed")
