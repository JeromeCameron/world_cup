import os
from datetime import date

import pandas as pd
import streamlit as st

from utils.auth import get_user_map, require_login

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

require_login()

UNLOCK_DATE = date(2026, 6, 9)

st.header("View Predictions")
st.caption("See what everyone predicted before the tournament started.")

if date.today() < UNLOCK_DATE:
    st.info("Predictions will be visible from **June 9th, 2026** once the submission deadline has passed.")
    st.stop()

# -------  Data  ---------------------------------------------------------------
ms = pd.read_json("assets/json/matches.json")[
    ["match_no", "team_a", "team_b", "stage", "group"]
]

# -------  User select  --------------------------------------------------------
user_map = get_user_map()
user_options = {firstname: username for username, firstname in user_map.items()}
selected_name = st.selectbox("Select player", options=list(user_options.keys()))
selected_username = user_options[selected_name]

pred_path = f"assets/csv_files/predictions/{selected_username}.csv"

if not os.path.exists(pred_path):
    st.warning(f"{selected_name} has not submitted any predictions yet.")
    st.stop()

preds = pd.read_csv(pred_path)[["match_no", "team_a_score", "team_b_score", "penalty_winner"]]

display = ms.merge(preds, on="match_no", how="left")

# -------  Column config helpers  ----------------------------------------------
SCORE_COL = lambda label: st.column_config.NumberColumn(label=label, width="small", format="%d")
TEXT_COL  = lambda label: st.column_config.TextColumn(label=label)

GROUP_CONFIG = {
    "match_no":     st.column_config.NumberColumn(label="No.", width="small"),
    "team_a":       TEXT_COL("Team A"),
    "team_a_score": SCORE_COL("Score"),
    "team_b_score": SCORE_COL("Score"),
    "team_b":       TEXT_COL("Team B"),
    "stage":        None,
    "group":        None,
}

KNOCKOUT_CONFIG = {
    **GROUP_CONFIG,
    "penalty_winner": st.column_config.TextColumn(label="Pen.", width="small"),
}

DISPLAY_GROUP_COLS    = ["match_no", "team_a", "team_a_score", "team_b_score", "team_b", "stage", "group"]
DISPLAY_KNOCKOUT_COLS = ["match_no", "team_a", "team_a_score", "team_b_score", "team_b", "penalty_winner", "stage", "group"]

# -------  Group stage  --------------------------------------------------------
st.subheader("Group Stage")

group_data = display[display["stage"] == "group"]
groups = sorted(group_data["group"].dropna().unique().tolist())
tabs = st.tabs(groups)

for tab, grp in zip(tabs, groups):
    with tab:
        st.dataframe(
            group_data[group_data["group"] == grp][DISPLAY_GROUP_COLS],
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

knockout_data = display[display["stage"].isin(STAGE_LABELS)]
ko_tabs = st.tabs(list(STAGE_LABELS.values()))

for tab, (stage, _) in zip(ko_tabs, STAGE_LABELS.items()):
    with tab:
        stage_df = knockout_data[knockout_data["stage"] == stage]
        if stage_df.empty:
            st.caption("No matches for this stage.")
        else:
            st.dataframe(
                stage_df[DISPLAY_KNOCKOUT_COLS],
                hide_index=True,
                use_container_width=True,
                column_config=KNOCKOUT_CONFIG,
            )
