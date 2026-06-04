"""
Run this once to initialise the Supabase database.
Usage:
    SUPABASE_URL=https://xxx.supabase.co SUPABASE_KEY=your-service-key python seed_db.py
"""
import json
import os
import sys

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Set SUPABASE_URL and SUPABASE_KEY environment variables before running.")
    sys.exit(1)

client = create_client(url, key)

# ── Match results ──────────────────────────────────────────────────────────────
with open("assets/json/matches.json") as f:
    matches = json.load(f)

match_records = [
    {
        "match_no": m["match_no"],
        "team_a":   m["team_a"],
        "team_b":   m["team_b"],
        "team_a_score": None,
        "team_b_score": None,
        "penalty_winner": None,
        "stage": m.get("stage"),
        "group": m.get("group"),
    }
    for m in matches
]
client.table("match_results").upsert(match_records).execute()
print(f"✓ Seeded {len(match_records)} matches into match_results")

# ── Users ──────────────────────────────────────────────────────────────────────
client.table("users").upsert([{"username": "jimmy", "firstname": "Jimmy"}]).execute()
print("✓ Seeded users")

# ── Points table ───────────────────────────────────────────────────────────────
client.table("points_table").upsert([{
    "username": "jimmy", "firstname": "Jimmy",
    "winners_picked": 0, "scores_predicted": 0,
    "total_goals": 0, "goal_difference": 0, "bonus_points": 0.0,
}]).execute()
print("✓ Seeded points_table")

# ── Predictions ────────────────────────────────────────────────────────────────
pred_records = [
    {
        "username": "jimmy",
        "match_no": m["match_no"],
        "team_a_score": None,
        "team_b_score": None,
        "penalty_winner": None,
    }
    for m in matches
]
client.table("predictions").upsert(pred_records).execute()
print(f"✓ Seeded {len(pred_records)} blank predictions for jimmy")

print("\nDatabase seeded successfully!")
