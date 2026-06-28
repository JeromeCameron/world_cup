import pandas as pd
import streamlit as st

from utils.auth import get_user_map, require_login
from utils.db import get_points_audit_for_user, get_points_table

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

require_login()

CATEGORY_COLS = [
    "winners_picked",
    "scores_predicted",
    "total_goals",
    "goal_difference",
    "bonus_points",
]

COLUMN_LABELS = {
    "rank": "Rank",
    "firstname": "Name",
    "winners_picked": "Winners",
    "scores_predicted": "Score",
    "total_goals": "Goals",
    "goal_difference": "GD",
    "bonus_points": "Bonus",
    "total_points": "Total",
}

RANK_ICONS = {1: "🥇", 2: "🥈", 3: "🥉"}


def load_leaderboard() -> pd.DataFrame:
    data = get_points_table()
    df = pd.DataFrame(data)
    user_map = get_user_map()
    df["firstname"] = df["username"].map(user_map).fillna(df.get("firstname", df["username"]))
    df["total_points"] = df[CATEGORY_COLS].sum(axis=1)
    df = df.sort_values(
        ["total_points", "winners_picked", "scores_predicted", "goal_difference", "total_goals"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    df.index += 1
    df.insert(0, "rank", df.index.map(lambda i: f"{RANK_ICONS.get(i, i)}"))
    return df[["rank", "firstname"] + CATEGORY_COLS + ["total_points"]]


st.header("Leaderboard")
st.caption("Updated after each match result is entered.")

df = load_leaderboard()


def _style_leaderboard(df: pd.DataFrame):
    def row_style(row):
        if row.name <= 3:
            return ["font-weight: 700"] * len(row)
        return ["color: #9e9e9e"] * len(row)
    return df.style.apply(row_style, axis=1)


st.dataframe(
    _style_leaderboard(df),
    hide_index=True,
    use_container_width=True,
    column_config={
        k: st.column_config.TextColumn(label=v)
        if k in ("rank", "firstname")
        else st.column_config.NumberColumn(label=v, format="%.2f")
        if k in ("bonus_points", "total_points")
        else st.column_config.NumberColumn(label=v)
        for k, v in COLUMN_LABELS.items()
    },
)

st.caption(
    "Points per match: Winner (2) · Exact Score (3) · Total Goals (2) · Goal Difference (1) · R32 Qualifier (0.5) · Knockout winner/wrong opponent (1)"
)

# -------  Audit  --------------------------------------------------------------
st.divider()
st.subheader("Points Breakdown")

table_data = get_points_table()

matches_df = pd.read_json("assets/json/matches.json")[
    ["match_no", "team_a", "team_b", "stage", "group"]
]

user_map = get_user_map()
user_options = {user_map.get(row["username"], row["username"]): row["username"] for row in table_data}
selected_name = st.selectbox("Select player", options=list(user_options.keys()))
selected_username = user_options[selected_name]

entries = get_points_audit_for_user(selected_username)

if not entries:
    st.info("No match results have been entered yet.")
else:
    audit_df = pd.DataFrame(entries)
    audit_df = audit_df[(audit_df["total"] > 0) | audit_df["match_no"].isna()]
    audit_df = audit_df.merge(matches_df, on="match_no", how="left")
    audit_df["match"] = audit_df.apply(
        lambda r: "R32 Qualification Bonus"
        if pd.isna(r["match_no"])
        else f"{r['team_a']} vs {r['team_b']}",
        axis=1,
    )
    audit_df["stage"] = audit_df["stage"].fillna("bonus")

    st.dataframe(
        audit_df[
            [
                "match_no",
                "match",
                "stage",
                "winners_picked",
                "scores_predicted",
                "total_goals",
                "goal_difference",
                "bonus_points",
                "total",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        column_config={
            "match_no": st.column_config.NumberColumn(label="Match"),
            "match": st.column_config.TextColumn(label="Match"),
            "stage": st.column_config.TextColumn(label="Stage"),
            "winners_picked": st.column_config.NumberColumn(label="Winners"),
            "scores_predicted": st.column_config.NumberColumn(label="Score"),
            "total_goals": st.column_config.NumberColumn(label="Goals"),
            "goal_difference": st.column_config.NumberColumn(label="GD"),
            "bonus_points": st.column_config.NumberColumn(label="Bonus"),
            "total": st.column_config.NumberColumn(label="Total"),
        },
    )
