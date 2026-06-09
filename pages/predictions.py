from datetime import date, datetime, timezone

import pandas as pd
import streamlit as st

from util import (
    build_all_knockout_stages,
    build_prediction_fixtures,
    calculate_group_qualifiers,
    calculate_standings,
    render_standings_table,
)
from utils.auth import require_login
from utils.db import ensure_predictions_exist, get_predictions, save_predictions

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


LOCK_DATE = date(2026, 6, 10)

# -------  Auth  ---------------------------------------------------------------
selected_user = require_login()

if datetime.now(timezone.utc).date() >= LOCK_DATE:
    st.header("Predictions 🧠")
    st.info("The prediction deadline has passed. Predictions are now locked.")
    st.stop()
ensure_predictions_exist(selected_user)
user_preds = get_predictions(selected_user)
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

KO_STAGES = ["round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final"]


def _has_unsaved_changes() -> bool:
    saved = (
        user_preds[["match_no", "team_a_score", "team_b_score"]]
        .fillna(-1)
        .astype(float)
        .set_index("match_no")
    )
    for key in [f"editor_{g}" for g in groups] + [f"ko_{s}" for s in KO_STAGES]:
        edited = st.session_state.get(key)
        if not isinstance(edited, pd.DataFrame) or "match_no" not in edited.columns:
            continue
        e = (
            edited[["match_no", "team_a_score", "team_b_score"]]
            .fillna(-1)
            .astype(float)
            .set_index("match_no")
            .sort_index()
        )
        s = saved.loc[saved.index.isin(e.index)].sort_index()
        if not e.equals(s):
            return True
    return False


# -------  Groups Input  -------------------------------------------------------
total_matches = len(user_preds)
filled = int(user_preds[["team_a_score", "team_b_score"]].notna().all(axis=1).sum())

st.header("Predictions 🧠")
st.caption(f"{filled} of {total_matches} matches predicted")
st.progress(filled / total_matches if total_matches > 0 else 0)

if st.session_state.pop("groups_saved", False):
    st.toast("Group predictions saved!", icon="✅")

if _has_unsaved_changes():
    st.warning("You have unsaved changes — click **Save Changes** to keep them.", icon="⚠️")

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

if st.button("Save Groups"):
    group_edits["penalty_winner"] = None
    remaining = user_preds[~user_preds["match_no"].isin(group_edits["match_no"])]
    saved = pd.concat([group_edits, remaining], ignore_index=True).sort_values("match_no")
    save_predictions(selected_user, saved)
    st.session_state["groups_saved"] = True
    st.rerun()

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

if st.button("Save Changes"):
    group_edits["penalty_winner"] = None
    all_edits = pd.concat([group_edits] + knockout_edits, ignore_index=True)
    remaining = user_preds[~user_preds["match_no"].isin(all_edits["match_no"])]
    saved = pd.concat([all_edits, remaining], ignore_index=True).sort_values("match_no")
    save_predictions(selected_user, saved)
    for stage in stage_labels:
        st.session_state.pop(f"ko_{stage}", None)
    st.session_state["knockout_saved"] = True
    st.rerun()

if st.session_state.pop("knockout_saved", False):
    st.toast("Knockout predictions saved!", icon="✅")
