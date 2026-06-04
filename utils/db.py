import json

import pandas as pd
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def _client() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


def _records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a JSON-safe list of dicts."""
    result = []
    for _, row in df.iterrows():
        r = {}
        for col, val in row.items():
            if pd.isna(val):
                r[col] = None
            elif hasattr(val, "item"):
                r[col] = val.item()  # convert numpy scalar to Python native
            else:
                r[col] = val
        result.append(r)
    return result


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    rows = (
        _client().table("users").select("*").eq("username", username).execute().data
    )
    return rows[0] if rows else None


def set_user_password(username: str, password_hash: str) -> None:
    from datetime import datetime, timezone
    _client().table("users").update({
        "password_hash": password_hash,
        "last_login": datetime.now(timezone.utc).isoformat(),
    }).eq("username", username).execute()


def update_last_login(username: str) -> None:
    from datetime import datetime, timezone
    _client().table("users").update({
        "last_login": datetime.now(timezone.utc).isoformat(),
    }).eq("username", username).execute()


def get_user_map() -> dict[str, str]:
    rows = _client().table("users").select("username, firstname").execute().data
    return {r["username"]: r["firstname"] for r in rows}


def get_firstname(username: str) -> str:
    rows = (
        _client()
        .table("users")
        .select("firstname")
        .eq("username", username)
        .execute()
        .data
    )
    return rows[0]["firstname"] if rows else username


def add_user(username: str, firstname: str) -> None:
    c = _client()
    c.table("users").insert({"username": username, "firstname": firstname}).execute()
    c.table("points_table").insert({
        "username": username,
        "firstname": firstname,
        "winners_picked": 0,
        "scores_predicted": 0,
        "total_goals": 0,
        "goal_difference": 0,
        "bonus_points": 0.0,
    }).execute()
    with open("assets/json/matches.json") as f:
        matches = json.load(f)
    rows = [
        {
            "username": username,
            "match_no": m["match_no"],
            "team_a_score": None,
            "team_b_score": None,
            "penalty_winner": None,
        }
        for m in matches
    ]
    c.table("predictions").insert(rows).execute()


# ── Match results ──────────────────────────────────────────────────────────────

def get_match_results() -> pd.DataFrame:
    data = _client().table("match_results").select("*").order("match_no").execute().data
    return pd.DataFrame(data) if data else pd.DataFrame()


def save_match_results(df: pd.DataFrame) -> None:
    _client().table("match_results").upsert(_records(df)).execute()


# ── Predictions ────────────────────────────────────────────────────────────────

def ensure_predictions_exist(username: str) -> None:
    """Creates blank prediction rows for all matches if the user has none yet."""
    c = _client()
    existing = (
        c.table("predictions")
        .select("match_no")
        .eq("username", username)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return
    with open("assets/json/matches.json") as f:
        matches = json.load(f)
    rows = [
        {
            "username": username,
            "match_no": m["match_no"],
            "team_a_score": None,
            "team_b_score": None,
            "penalty_winner": None,
        }
        for m in matches
    ]
    c.table("predictions").insert(rows).execute()


def get_predictions(username: str) -> pd.DataFrame:
    data = (
        _client()
        .table("predictions")
        .select("match_no, team_a_score, team_b_score, penalty_winner")
        .eq("username", username)
        .order("match_no")
        .execute()
        .data
    )
    if not data:
        return pd.DataFrame(
            columns=["match_no", "team_a_score", "team_b_score", "penalty_winner"]
        )
    return pd.DataFrame(data)


def save_predictions(username: str, df: pd.DataFrame) -> None:
    cols = ["match_no", "team_a_score", "team_b_score", "penalty_winner"]
    records = _records(df[cols])
    for r in records:
        r["username"] = username
    _client().table("predictions").upsert(records).execute()


# ── Points ─────────────────────────────────────────────────────────────────────

def get_points_table() -> list[dict]:
    return _client().table("points_table").select("*").execute().data


def get_points_audit() -> dict[str, list]:
    data = (
        _client().table("points_audit").select("*").order("id").execute().data
    )
    result: dict[str, list] = {}
    for row in data:
        username = row["username"]
        entry = {k: v for k, v in row.items() if k not in ("id", "username")}
        result.setdefault(username, []).append(entry)
    return result


def save_points(table_data: list[dict], audit_data: dict[str, list]) -> None:
    c = _client()
    c.table("points_table").upsert(table_data).execute()
    # Replace all audit rows
    c.table("points_audit").delete().gte("id", 0).execute()
    rows = []
    for username, entries in audit_data.items():
        for entry in entries:
            row = {"username": username}
            row.update({k: v for k, v in entry.items() if k != "id"})
            rows.append(row)
    if rows:
        c.table("points_audit").insert(rows).execute()
