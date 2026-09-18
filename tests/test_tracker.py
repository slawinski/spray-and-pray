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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
