"""Tests for the Sankey ghosted-exclusion logic and rendering."""
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_optimizer.sankey import build_sankey_flows, _clean_ghosted, render_sankey


def test_ghosted_terminal():
    """ghosted as terminal status → kept."""
    chain = ["applied", "ghosted"]
    assert _clean_ghosted(chain) == ["applied", "ghosted"]


def test_ghosted_with_subsequent():
    """ghosted followed by non-ghosted → ghosted removed."""
    chain = ["applied", "ghosted", "interview 1", "rejected"]
    assert _clean_ghosted(chain) == ["applied", "interview 1", "rejected"]


def test_ghosted_multiple_with_subsequent():
    """Multiple ghosted entries, non-ghosted after first → all ghosted removed."""
    chain = ["applied", "ghosted", "interview 1", "ghosted"]
    assert _clean_ghosted(chain) == ["applied", "interview 1"]


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


if __name__ == "__main__":
    test_ghosted_terminal()
    test_ghosted_with_subsequent()
    test_ghosted_multiple_with_subsequent()
    test_no_ghosted()
    test_build_flows_spec_example_1()
    test_build_flows_spec_example_2()
    test_build_flows_aggregation()
    test_render_sankey_empty()
    test_render_sankey_output()
    print("✓ All 9 tests passed")
