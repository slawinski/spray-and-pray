"""Integration smoke test for DB + tracker + sankey pipeline."""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use a temp DB so we don't pollute the real one
import cv_optimizer.db as db
tmpdir = tempfile.mkdtemp()
db.DB_PATH = Path(tmpdir) / "test.db"

from cv_optimizer.sankey import build_sankey_flows, render_sankey


def test_full_pipeline():
    db.init_db()

    # Simulate 5 applications
    # App 1: applied → ghosted (terminal)
    a1 = db.insert_application("Google", "SWE")
    db.insert_status(a1, "applied")
    db.insert_status(a1, "ghosted")

    # App 2: applied → ghosted → interview 1 → rejected (ghosted excluded)
    a2 = db.insert_application("Meta", "Frontend")
    db.insert_status(a2, "applied")
    db.insert_status(a2, "ghosted")
    db.insert_status(a2, "interview 1")
    db.insert_status(a2, "rejected")

    # App 3: applied → ghosted → interview 1 → interview 2 → offer → accepted
    a3 = db.insert_application("Stripe", "Fullstack")
    db.insert_status(a3, "applied")
    db.insert_status(a3, "ghosted")
    db.insert_status(a3, "interview 1")
    db.insert_status(a3, "interview 2")
    db.insert_status(a3, "offer")
    db.insert_status(a3, "accepted")

    # App 4: applied → ghosted (terminal)
    a4 = db.insert_application("Netflix", "SRE")
    db.insert_status(a4, "applied")
    db.insert_status(a4, "ghosted")

    # App 5: applied → interview 1 → rejected (no ghosted at all)
    a5 = db.insert_application("Spotify", "Backend")
    db.insert_status(a5, "applied")
    db.insert_status(a5, "interview 1")
    db.insert_status(a5, "rejected")

    # Build flows
    transitions = db.get_all_transitions()
    flows = build_sankey_flows(transitions)

    # Verify expected transitions
    assert flows[("applied", "ghosted")] == 2, f"Expected 2, got {flows.get(('applied', 'ghosted'))}"
    assert flows[("applied", "interview 1")] == 3, f"Expected 3, got {flows.get(('applied', 'interview 1'))}"
    assert flows[("interview 1", "rejected")] == 2, f"Expected 2, got {flows.get(('interview 1', 'rejected'))}"
    assert flows[("interview 1", "interview 2")] == 1
    assert flows[("interview 2", "offer")] == 1
    assert flows[("offer", "accepted")] == 1

    # Render and print
    output = render_sankey(flows)
    print(output)
    print()
    
    # Verify list_applications
    apps = db.list_applications()
    assert len(apps) == 5

    # Verify get_application
    app = db.get_application(a1)
    assert app is not None
    assert app[1] == "Google"

    # Verify update_application
    db.update_application(a1, jd_path="/tmp/jd.pdf")
    app = db.get_application(a1)
    assert app[3] == "/tmp/jd.pdf"

    print("✓ All integration tests passed")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_full_pipeline()
