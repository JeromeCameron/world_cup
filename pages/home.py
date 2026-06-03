import pandas as pd
import streamlit as st

from util import calculate_standings, render_knockout_bracket, render_standings_table
from utils.auth import require_login

require_login()

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

GROUPS: list[str] = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]

st.header("Predict & Win: World Cup 2026")
st.caption("Enter your predictions and compete for the ultimate prize: four years of bragging rights 🏆")

st.markdown("We are back at it again — but this time in a whole new format… no more Excel spreadsheets 😅⚽")

st.divider()
st.subheader("Points System")

points_df = pd.DataFrame({
    "Category": [
        "Match Winner",
        "Match Score",
        "Total Goals Scored",
        "Goal Difference",
        "R32 Qualifier (per team)",
    ],
    "Points": [2, 3, 2, 1, 0.5],
    "Description": [
        "Correctly predicted the winning team (or draw)",
        "Correctly predicted the exact final score",
        "Correctly predicted the total number of goals scored",
        "Correctly predicted the goal difference between the two teams",
        "Correctly predicted a team to qualify for the Round of 32",
    ],
})
st.dataframe(
    points_df.style
    .map(lambda _: "font-weight: bold", subset=["Points"])
    .set_table_styles([{"selector": "th", "props": [("font-weight", "bold"), ("text-align", "center")]}]),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Category": st.column_config.TextColumn(),
        "Points": st.column_config.NumberColumn(format="%g"),
        "Description": st.column_config.TextColumn(),
    },
)

ms = pd.read_json("assets/json/matches.json")
actual = pd.read_json("assets/json/match_results.json")

group_fixtures = ms[ms["group"].notna()][["match_no", "team_a", "team_b", "group"]].copy()
actual_with_teams = group_fixtures.merge(
    actual[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
)

st.divider()
st.subheader("Tournament")
with st.expander("Groups", expanded=False):
    for group in GROUPS:
        group_df = actual_with_teams[actual_with_teams["group"] == group]
        standings = calculate_standings(group_df)
        st.markdown(render_standings_table(standings, group), unsafe_allow_html=True)

with st.expander("Knockout Bracket", expanded=False):
    st.caption("Updates automatically as match results are entered.")
    knockout = actual[actual["stage"] != "group"]
    st.markdown(render_knockout_bracket(knockout), unsafe_allow_html=True)
