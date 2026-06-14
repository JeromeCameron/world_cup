import pandas as pd
import streamlit as st

from util import (
    build_all_knockout_stages,
    build_prediction_fixtures,
    calculate_group_qualifiers,
    calculate_standings,
)
from utils.auth import require_login
from utils.db import add_user, get_match_results, get_user_map, save_match_results  # delete_user, get_predictions_summary
from utils.points_calc import recalculate_all_points

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

ADMIN_USERNAME = "jimmy"

selected_user = require_login()

if st.session_state.pop("results_saved", False):
    st.toast("Results saved and points recalculated.", icon="✅")

if selected_user != ADMIN_USERNAME:
    st.error("You do not have permission to view this page.")
    st.stop()

# -------  Data  ---------------------------------------------------------------
results = get_match_results()
results.sort_values("match_no", inplace=True)

STAGE_LABELS = {
    "group": "Group Stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter Finals",
    "semi_final": "Semi Finals",
    "third_place": "Third Place",
    "final": "Final",
}

DISPLAY_COLS = [
    "match_no", "team_a", "team_a_score", "team_b_score", "team_b",
]
KNOCKOUT_DISPLAY_COLS = DISPLAY_COLS + ["penalty_winner"]

BASE_CONFIG = {
    "match_no":     st.column_config.NumberColumn(label="No.", width="small"),
    "team_a":       st.column_config.TextColumn(label="Team A"),
    "team_a_score": st.column_config.NumberColumn(label="Score", width="small"),
    "team_b_score": st.column_config.NumberColumn(label="Score", width="small"),
    "team_b":       st.column_config.TextColumn(label="Team B"),
}
KNOCKOUT_CONFIG = {
    **BASE_CONFIG,
    "penalty_winner": st.column_config.SelectboxColumn(
        label="Pen.", options=["A", "B"], required=False, width="small"
    ),
}

DISABLED = ["match_no", "team_a", "team_b"]

# -------  Editors  ------------------------------------------------------------
st.header("Admin: Enter Results")
st.caption("Enter actual match scores to update the leaderboard and resolve knockout stage brackets.")

# -------  Prediction completion  ----------------------------------------------
# st.subheader("Prediction Completion")
# summary = get_predictions_summary()
# user_map = get_user_map()
# summary["Name"] = summary["username"].map(user_map).fillna(summary["username"])
# summary = summary.sort_values(["pct", "Name"], ascending=[False, True]).reset_index(drop=True)
# summary["Progress"] = summary["filled"].astype(str) + " / " + summary["total"].astype(str)
# st.dataframe(
#     summary[["Name", "pct", "Progress"]],
#     hide_index=True,
#     use_container_width=True,
#     column_config={
#         "Name": st.column_config.TextColumn(label="Player"),
#         "pct": st.column_config.ProgressColumn(
#             label="Completion",
#             format="%.0f%%",
#             min_value=0,
#             max_value=100,
#         ),
#         "Progress": st.column_config.TextColumn(label="Predicted"),
#     },
# )
# st.divider()

groups = results["group"].dropna().unique().tolist()
edited_dfs: list[pd.DataFrame] = []

st.subheader("Group Stage")
group_tabs = st.tabs(groups)
for tab, grp in zip(group_tabs, groups):
    with tab:
        grp_df = results[results["group"] == grp]
        edited = st.data_editor(
            grp_df[DISPLAY_COLS],
            hide_index=True,
            use_container_width=True,
            column_config=BASE_CONFIG,
            disabled=DISABLED,
            key=f"admin_group_{grp}",
        )
        edited_dfs.append(edited[["match_no", "team_a_score", "team_b_score"]])

st.subheader("Knockout Stage")
knockout_stages = [s for s in STAGE_LABELS if s != "group"]
ko_tabs = st.tabs([STAGE_LABELS[s] for s in knockout_stages])
for tab, stage in zip(ko_tabs, knockout_stages):
    with tab:
        stage_df = results[results["stage"] == stage]
        if stage_df.empty:
            st.caption("No matches scheduled for this stage yet.")
            continue
        if "penalty_winner" not in stage_df.columns:
            stage_df = stage_df.copy()
            stage_df["penalty_winner"] = None
        edited = st.data_editor(
            stage_df[KNOCKOUT_DISPLAY_COLS],
            hide_index=True,
            use_container_width=True,
            column_config=KNOCKOUT_CONFIG,
            disabled=DISABLED,
            key=f"admin_ko_{stage}",
        )
        edited_dfs.append(
            edited[["match_no", "team_a_score", "team_b_score", "penalty_winner"]]
        )

# -------  Save  ---------------------------------------------------------------
if st.button("Save & Recalculate Points", type="primary"):
    all_edits = pd.concat(edited_dfs, ignore_index=True).drop_duplicates("match_no")

    full = get_match_results()
    full.set_index("match_no", inplace=True)
    all_edits.set_index("match_no", inplace=True)

    update_cols = ["team_a_score", "team_b_score"]
    if "penalty_winner" in all_edits.columns:
        if "penalty_winner" not in full.columns:
            full["penalty_winner"] = None
        update_cols.append("penalty_winner")

    full.update(all_edits[update_cols])
    full.reset_index(inplace=True)

    # Resolve team progressions into knockout rounds
    ms = pd.read_json("assets/json/matches.json")
    actual = full.copy()

    group_played = actual[
        actual["group"].notna()
        & actual["team_a_score"].notna()
        & actual["team_b_score"].notna()
    ].copy()

    standings_by_group = {
        grp: calculate_standings(gdf)
        for grp, gdf in group_played.groupby("group")
    }
    qualifiers = calculate_group_qualifiers(standings_by_group)
    all_fixtures = build_prediction_fixtures(ms, qualifiers, actual)
    resolved_stages = build_all_knockout_stages(all_fixtures)

    actual.set_index("match_no", inplace=True)
    for stage_df in resolved_stages.values():
        actual.update(stage_df.set_index("match_no")[["team_a", "team_b"]])
    actual.reset_index(inplace=True)
    save_match_results(actual)

    recalculate_all_points()

    for key in list(st.session_state.keys()):
        if key.startswith("admin_"):
            st.session_state.pop(key)

    st.session_state["results_saved"] = True
    st.rerun()

# -------  Add User  -----------------------------------------------------------
st.divider()
st.subheader("Add New User")

with st.form("add_user_form"):
    new_username = st.text_input("Username", placeholder="e.g. jsmith")
    new_firstname = st.text_input("First Name", placeholder="e.g. John")
    add_submitted = st.form_submit_button("Add User")

if add_submitted:
    username = new_username.strip().lower()
    firstname = new_firstname.strip()

    if not username or not firstname:
        st.error("Both username and first name are required.")
    else:
        if username in get_user_map():
            st.error(f"Username '{username}' already exists.")
        else:
            add_user(username, firstname)
            st.success(f"User '{firstname}' ({username}) added successfully.")
            st.rerun()

# -------  Delete User  --------------------------------------------------------
# st.divider()
# st.subheader("Delete User")
#
# deletable_users = {v: k for k, v in get_user_map().items() if k != ADMIN_USERNAME}
#
# if not deletable_users:
#     st.caption("No other users to delete.")
# else:
#     selected_delete = st.selectbox("Select user to delete", options=list(deletable_users.keys()))
#
#     if st.button("Delete User", type="primary"):
#         st.session_state["confirm_delete"] = selected_delete
#
#     if st.session_state.get("confirm_delete") == selected_delete:
#         st.warning(f"Are you sure you want to delete **{selected_delete}**? This will remove all their predictions and points and cannot be undone.")
#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("Yes, delete", type="primary", use_container_width=True):
#                 delete_user(deletable_users[selected_delete])
#                 st.session_state.pop("confirm_delete", None)
#                 st.toast(f"User '{selected_delete}' deleted.", icon="✅")
#                 st.rerun()
#         with col2:
#             if st.button("Cancel", use_container_width=True):
#                 st.session_state.pop("confirm_delete", None)
#                 st.rerun()
