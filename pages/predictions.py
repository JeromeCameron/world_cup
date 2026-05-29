import pandas as pd
import streamlit as st

from util import (
    build_all_knockout_stages,
    build_prediction_fixtures,
    calculate_group_qualifiers,
    calculate_standings,
    generate_predictions_file,
    render_standings_table,
)
from utils.auth import require_login

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

ms = pd.read_json("assets/json/matches.json")
matches = ms.copy()
matches.sort_values(by="match_no", inplace=True)

groups = matches["group"].dropna().unique().tolist()
matches = matches.drop(columns=["match_date", "match_time", "time_local", "stage"])
matches = matches[
    [
        "match_no",
        "team_a",
        "team_a_score",
        "team_b_score",
        "team_b",
        "group",
    ]
]


# -------  Auth  ---------------------------------------------------------------
selected_user = require_login()
generate_predictions_file(selected_user)
user_pred_path = f"assets/csv_files/predictions/{selected_user}.csv"
user_preds = pd.read_csv(user_pred_path)
if "penalty_winner" not in user_preds.columns:
    user_preds["penalty_winner"] = None

# Merge user scores into fixture display data
display_matches = matches.drop(columns=["team_a_score", "team_b_score"]).merge(
    user_preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
)[["match_no", "team_a", "team_a_score", "team_b_score", "team_b", "group"]]

# Join predictions with fixture data for standings (adds team names + group)
group_fixtures = ms[ms["group"].notna()][
    ["match_no", "team_a", "team_b", "group"]
].copy()
pred_with_teams = group_fixtures.merge(
    user_preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
)

# -------  Groups Input  -------------------------------------------------------
st.header("Predictions 🧠")
st.subheader("Group Stage")
st.markdown(
    "Enter scores for each match in your group, then click **Save** to update your standings and fill in the Round of 32.",
    unsafe_allow_html=True,
)

tabs = st.tabs(groups)

edited_dfs = []
for tab, value in zip(tabs, groups):
    with tab:
        st.subheader("Group " + value)
        filtered_df = display_matches[display_matches["group"] == value]
        edited_df = st.data_editor(
            filtered_df,
            hide_index=True,
            column_config={
                "group": None,
                "match_no": st.column_config.NumberColumn(
                    label="Match No.", width="small"
                ),
                "team_a_score": st.column_config.NumberColumn(
                    label="Score", width="small"
                ),
                "team_b_score": st.column_config.NumberColumn(
                    label="Score", width="small"
                ),
                "team_a": st.column_config.TextColumn(label="Team A"),
                "team_b": st.column_config.TextColumn(label="Team B"),
            },
            disabled=["Match No.", "team_a", "team_b"],
            key=f"editor_{value}",
        )
        edited_dfs.append(edited_df)

        group_df = pred_with_teams[pred_with_teams["group"] == value]
        has_predictions = group_df[["team_a_score", "team_b_score"]].notna().any().any()
        if has_predictions:
            standings = calculate_standings(group_df)
            st.caption(f"Group {value} table based on your predictions")
            st.markdown(
                render_standings_table(standings, value), unsafe_allow_html=True
            )

group_edits = pd.concat(edited_dfs, ignore_index=True)[
    ["match_no", "team_a_score", "team_b_score"]
]

st.divider()
# -------  Knockout Stages  ----------------------------------------------------
standings_by_group = {}
for group, group_df in pred_with_teams.groupby("group"):
    standings_by_group[group] = calculate_standings(group_df)
qualifiers = calculate_group_qualifiers(standings_by_group)

st.subheader("Knockout Stage")

st.markdown(
    "Enter your scores for each match in a stage and click **Save** to update which teams progress to the next stage."
)
st.caption(
    "Note: If you predict a match will be decided by penalties, enter the scores and select Team A or Team B in the Penalty column to indicate who wins the shootout."
)
all_fixtures = build_prediction_fixtures(ms, qualifiers, user_preds)
knockout_stages = build_all_knockout_stages(all_fixtures)

stage_labels = {
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter Finals",
    "semi_final": "Semi Finals",
    "third_place": "Third Place",
    "final": "Final",
}

tabs = st.tabs(list(stage_labels.values()))
knockout_edits = []

for tab, (stage, label) in zip(tabs, stage_labels.items()):
    with tab:
        if stage in knockout_stages:
            edited = st.data_editor(
                knockout_stages[stage][
                    [
                        "match_no",
                        "team_a",
                        "team_a_score",
                        "team_b_score",
                        "team_b",
                        "penalty_winner",
                    ]
                ],
                hide_index=True,
                column_config={
                    "match_no": st.column_config.NumberColumn(
                        label="Match No.", width="small"
                    ),
                    "team_a": st.column_config.TextColumn(label="Team A"),
                    "team_a_score": st.column_config.NumberColumn(
                        label="Score", width="small"
                    ),
                    "team_b_score": st.column_config.NumberColumn(
                        label="Score", width="small"
                    ),
                    "team_b": st.column_config.TextColumn(label="Team B"),
                    "penalty_winner": st.column_config.SelectboxColumn(
                        label="Penalty.",
                        options=["A", "B"],
                        required=False,
                        width="small",
                    ),
                },
                disabled=["match_no", "team_a", "team_b"],
                key=f"ko_{stage}",
            )
            knockout_edits.append(
                edited[["match_no", "team_a_score", "team_b_score", "penalty_winner"]]
            )

if st.session_state.pop("predictions_saved", False):
    st.success("Changes saved!", icon="✅")

if st.button("Save Changes"):
    group_edits["penalty_winner"] = None
    all_edits = pd.concat([group_edits] + knockout_edits, ignore_index=True)
    remaining = user_preds[~user_preds["match_no"].isin(all_edits["match_no"])]
    saved = pd.concat([all_edits, remaining], ignore_index=True).sort_values("match_no")
    saved.to_csv(user_pred_path, index=False)
    for stage in stage_labels:
        st.session_state.pop(f"ko_{stage}", None)
    st.session_state["predictions_saved"] = True
    st.rerun()
