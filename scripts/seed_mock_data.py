"""Seed the database with realistic mock transitions for Sankey diagram visualization."""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "applications.db"

APPS = [
    ("Google", "Staff Engineer"),
    ("Meta", "Senior Frontend Engineer"),
    ("Stripe", "Backend Engineer"),
    ("Airbnb", "Senior iOS Engineer"),
    ("Netflix", "Platform Engineer"),
    ("Uber", "Staff Android Engineer"),
    ("Spotify", "Data Engineer"),
    ("Dropbox", "Senior Full Stack Engineer"),
    ("Twitter", "ML Engineer"),
    ("Shopify", "Senior DevOps Engineer"),
    ("Reddit", "Staff Backend Engineer"),
    ("Square", "Senior Product Engineer"),
    ("Notion", "Frontend Engineer"),
    ("Figma", "Design Engineer"),
    ("Vercel", "Senior Software Engineer"),
    ("Datadog", "Staff SRE"),
    ("GitLab", "Senior Security Engineer"),
    ("Coinbase", "Blockchain Engineer"),
    ("Atlassian", "Principal Engineer"),
    ("Supabase", "Full Stack Engineer"),
]

TRANSITION_CHAINS = [
    ["applied", "interview 1", "interview 2", "offer", "accepted"],
    ["applied", "interview 1", "interview 2", "rejected"],
    ["applied", "interview 1", "ghosted"],
    ["applied", "interview 1", "interview 2", "offer", "accepted"],
    ["applied", "ghosted"],
    ["applied", "interview 1", "interview 2", "interview 3", "offer"],
    ["applied", "rejected"],
    ["applied", "interview 1", "interview 2", "offer", "accepted"],
    ["applied", "interview 1", "rejected"],
    ["applied", "ghosted"],
    ["applied", "interview 1", "interview 2", "offer"],
    ["applied", "interview 1", "ghosted"],
    ["applied", "interview 1", "interview 2", "rejected"],
    ["applied", "interview 1", "offer", "accepted"],
    ["applied", "ghosted"],
    ["applied", "interview 1", "interview 2", "interview 3", "offer"],
    ["applied", "rejected"],
    ["applied", "interview 1", "interview 2", "offer", "accepted"],
    ["applied", "interview 1", "rejected"],
    ["applied", "interview 1", "interview 2", "ghosted"],
]

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys=ON")

for i, (company, role) in enumerate(APPS):
    created = datetime(2026, 6, 1) + timedelta(hours=i * 12)
    cursor = conn.execute(
        "INSERT INTO applications (company, role, created_at) VALUES (?, ?, ?)",
        (company, role, created.isoformat()),
    )
    app_id = cursor.lastrowid

    chain = TRANSITION_CHAINS[i]
    for j, status in enumerate(chain):
        ts = created + timedelta(hours=j * 24 + j * 6)
        conn.execute(
            "INSERT INTO status_history (application_id, status, transitioned_at) VALUES (?, ?, ?)",
            (app_id, status, ts.isoformat()),
        )

conn.commit()
conn.close()
print(f"Seeded {len(APPS)} applications with mock transitions.")
