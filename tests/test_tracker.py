"""Tests for tracker.update_status flow constraints (draft must pass through applied)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _history(db, app_id):
    return [row[1] for row in db.get_status_history_with_ids(app_id)]


def test_draft_to_applied_activates_with_ghosted(temp_db):
    """draft → applied inserts both applied and the pessimistic ghosted default."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "applied")

    assert _history(db, app_id) == ["draft", "applied", "ghosted"]


def test_draft_to_ghosted_activates_first(temp_db):
    """draft → ghosted must not skip applied."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "ghosted")

    assert _history(db, app_id) == ["draft", "applied", "ghosted"]


def test_draft_to_rejected_goes_through_applied(temp_db):
    """draft → rejected must pass through applied (no draft → rejected edge)."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "rejected")

    assert _history(db, app_id) == ["draft", "applied", "rejected"]


def test_draft_to_interview_goes_through_applied(temp_db):
    """draft → interview must pass through applied (no draft → interview edge)."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "interview 1")

    assert _history(db, app_id) == ["draft", "applied", "interview 1"]


def test_draft_to_offer_and_accepted_go_through_applied(temp_db):
    """draft → offer / accepted must pass through applied."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "offer")
    tracker.update_status(app_id, "accepted")

    assert _history(db, app_id) == ["draft", "applied", "offer", "accepted"]


def test_sankey_has_no_draft_edges_at_all(temp_db):
    """End-to-end: a draft that jumps straight to an outcome must produce no
    draft edges — draft is stripped from the funnel entirely, and the chain
    still starts at applied."""
    from cv_optimizer import tracker
    from cv_optimizer.sankey import build_sankey_flows

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")
    tracker.update_status(app_id, "interview 1")

    flows = build_sankey_flows(db.get_all_transitions())

    assert ("draft", "interview 1") not in flows
    assert ("draft", "rejected") not in flows
    assert ("draft", "applied") not in flows
    assert ("applied", "interview 1") in flows
    assert flows[("applied", "interview 1")] == 1


def test_withdrawn_is_valid_status():
    """withdrawn validates and ranks as terminal (same tier as rejected)."""
    from cv_optimizer import tracker
    from cv_optimizer.db import status_rank

    assert tracker._validate_status("withdrawn") == "withdrawn"
    assert tracker._validate_status(" Withdrawn ") == "withdrawn"
    assert status_rank("withdrawn") == status_rank("rejected") == 99


def test_draft_to_withdrawn_goes_through_applied(temp_db):
    """draft → withdrawn must pass through applied (transient ghosted swapped out)."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "withdrawn")

    assert _history(db, app_id) == ["draft", "applied", "withdrawn"]


def test_applied_wait_to_withdrawn_swaps_ghosted(temp_db):
    """Withdrawing right after applying works despite the pessimistic ghosted default."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "applied")
    assert _history(db, app_id) == ["draft", "applied", "ghosted"]

    tracker.update_status(app_id, "withdrawn")

    assert _history(db, app_id) == ["draft", "applied", "withdrawn"]


def test_interview_to_withdrawn(temp_db):
    """applied → interview 1 → withdrawn keeps the full chain."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "interview 1")
    tracker.update_status(app_id, "withdrawn")

    assert _history(db, app_id) == ["draft", "applied", "interview 1", "withdrawn"]


def test_offer_to_withdrawn(temp_db):
    """Walking away with an offer on the table is allowed."""
    from cv_optimizer import tracker

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")

    tracker.update_status(app_id, "offer")
    tracker.update_status(app_id, "withdrawn")

    assert _history(db, app_id) == ["draft", "applied", "offer", "withdrawn"]


def test_withdrawn_from_post_engagement_ghosted_blocked(temp_db):
    """withdrawn from real silence-after-engagement is blocked and leaves history untouched."""
    import sqlite3

    from cv_optimizer import tracker
    from cv_optimizer.db import DB_PATH

    db = temp_db
    app_id = db.insert_application("Acme", "Frontend")
    db.insert_status(app_id, "draft")
    db.insert_status(app_id, "applied")
    db.insert_status(app_id, "interview 1")

    # Force the anomalous silence-after-engagement state, bypassing the
    # forward-only trigger (unreachable through update_status by design).
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TRIGGER IF EXISTS trg_status_forward_only")
    conn.execute(
        "INSERT INTO status_history (application_id, status) VALUES (?, ?)",
        (app_id, "ghosted"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="[Ww]ithdraw"):
        tracker.update_status(app_id, "withdrawn")

    assert _history(db, app_id) == ["draft", "applied", "interview 1", "ghosted"]


def test_withdrawn_appears_in_funnel_without_ghosted_edge(temp_db):
    """End-to-end: withdrawn renders as a terminal funnel node, never via ghosted."""
    from cv_optimizer import tracker
    from cv_optimizer.sankey import build_sankey_flows

    db = temp_db
    app1 = db.insert_application("Acme", "Frontend")
    db.insert_status(app1, "draft")
    tracker.update_status(app1, "withdrawn")

    app2 = db.insert_application("Beta", "Backend")
    db.insert_status(app2, "draft")
    tracker.update_status(app2, "interview 1")
    tracker.update_status(app2, "withdrawn")

    flows = build_sankey_flows(db.get_all_transitions())

    assert flows[("applied", "withdrawn")] == 1
    assert flows[("interview 1", "withdrawn")] == 1
    assert ("ghosted", "withdrawn") not in flows


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
