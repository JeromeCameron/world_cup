from datetime import date, datetime, timezone

import pandas as pd
import streamlit as st

from util import (
    build_all_knockout_stages,
    build_prediction_fixtures,
    calculate_group_qualifiers,
    calculate_standings,
)
from utils.auth import get_user_map, require_login
from utils.db import get_predictions

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

current_user = require_login()

UNLOCK_DATE = date(2026, 6, 11)

st.header("View Predictions")
st.caption("See what everyone predicted before the tournament started.")

if datetime.now(timezone.utc).date() < UNLOCK_DATE and current_user != "jimmy":
    st.info(
        "Predictions will be visible from **June 10th, 2026** once the submission deadline has passed."
    )
    st.stop()

# -------  Data  ---------------------------------------------------------------
ms = pd.read_json("assets/json/matches.json")

# -------  User select  --------------------------------------------------------
user_map = get_user_map()
user_options = {firstname: username for username, firstname in user_map.items()}
selected_name = st.selectbox("Select player", options=sorted(user_options.keys()))
selected_username = user_options[selected_name]

preds = get_predictions(selected_username)

if preds.empty or not preds[["team_a_score", "team_b_score"]].notna().any().any():
    st.warning(f"{selected_name} has not submitted any predictions yet.")
    st.stop()

# -------  Resolve knockout team names from group predictions  -----------------
group_fixtures = ms[ms["group"].notna()][
    ["match_no", "team_a", "team_b", "group"]
].copy()
pred_with_teams = group_fixtures.merge(
    preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
)

standings_by_group = {}
for group, group_df in pred_with_teams.groupby("group"):
    standings_by_group[group] = calculate_standings(group_df)

qualifiers = calculate_group_qualifiers(standings_by_group)
all_fixtures = build_prediction_fixtures(ms, qualifiers, preds)
knockout_stages = build_all_knockout_stages(all_fixtures)

# -------  Column config helpers  ----------------------------------------------
SCORE_COL = lambda label: st.column_config.NumberColumn(
    label=label, width="small", format="%d"
)
TEXT_COL = lambda label: st.column_config.TextColumn(label=label)

GROUP_CONFIG = {
    "match_no": st.column_config.NumberColumn(label="No.", width="small"),
    "team_a": TEXT_COL("Team A"),
    "team_a_score": SCORE_COL("Score"),
    "team_b_score": SCORE_COL("Score"),
    "team_b": TEXT_COL("Team B"),
    "stage": None,
    "group": None,
}

KNOCKOUT_CONFIG = {
    **GROUP_CONFIG,
    "penalty_winner": st.column_config.TextColumn(label="Pen.", width="small"),
}

DISPLAY_GROUP_COLS = [
    "match_no",
    "team_a",
    "team_a_score",
    "team_b_score",
    "team_b",
    "stage",
    "group",
]
DISPLAY_KNOCKOUT_COLS = [
    "match_no",
    "team_a",
    "team_a_score",
    "team_b_score",
    "team_b",
    "penalty_winner",
]

# -------  Group stage  --------------------------------------------------------
st.subheader("Group Stage")

group_display = ms[ms["stage"] == "group"][
    ["match_no", "team_a", "team_b", "stage", "group"]
].merge(preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left")
groups = sorted(group_display["group"].dropna().unique().tolist())
tabs = st.tabs(groups)

for tab, grp in zip(tabs, groups):
    with tab:
        st.dataframe(
            group_display[group_display["group"] == grp][DISPLAY_GROUP_COLS],
            hide_index=True,
            use_container_width=True,
            column_config=GROUP_CONFIG,
        )

# -------  Knockout stage  -----------------------------------------------------
st.subheader("Knockout Stage")

STAGE_LABELS = {
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter Finals",
    "semi_final": "Semi Finals",
    "third_place": "Third Place",
    "final": "Final",
}

ko_tabs = st.tabs(list(STAGE_LABELS.values()))

for tab, (stage, _) in zip(ko_tabs, STAGE_LABELS.items()):
    with tab:
        if stage not in knockout_stages:
            st.caption("No matches for this stage.")
        else:
            stage_df = knockout_stages[stage]
            if "penalty_winner" not in stage_df.columns:
                stage_df = stage_df.copy()
                stage_df["penalty_winner"] = None
            st.dataframe(
                stage_df[DISPLAY_KNOCKOUT_COLS],
                hide_index=True,
                use_container_width=True,
                column_config=KNOCKOUT_CONFIG,
            )
