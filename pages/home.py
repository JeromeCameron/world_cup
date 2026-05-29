import json

import pandas as pd
import streamlit as st

from util import load_groups
from utils.auth import require_login

require_login()

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

GROUPS: list[str] = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]

st.header("Predict & Win: World Cup 2026")

intro: str = """
    <p>
    We are back at it again — but this time in a whole new format… no more Excel spreadsheets 😅⚽
    </p>
    <p>
    Enter your World Cup 2026 predictions here and compete for the ultimate prize: four years of bragging rights 🏆🔥
    </p>
"""

points_system: str = """
    <h4>Points System</h4>
    <table style="width:70%; border: none; border-collapse: collapse;">
        <tr style="background-color: #E5E4E2; text-align: center; font-size:0.8rem;">
            <th style="padding: 8px; text-align: center;">Predicted Correctly</th>
            <th style="padding: 8px; text-align: center;">Points</th>
        </tr>
        <tr><td>Match Winner</td><td>2</td></tr>
        <tr><td>Match Score</td><td>3</td></tr>
        <tr><td>Total Goals Scored</td><td>2</td></tr>
        <tr><td>Goal Difference</td><td>1</td></tr>
    </table>
"""

st.markdown(intro, unsafe_allow_html=True)
st.markdown(points_system, unsafe_allow_html=True)
st.divider()

st.markdown("<h3>Groups</h3>", unsafe_allow_html=True)

with open("assets/json/groups.json") as f:
    data = json.load(f)

for group in GROUPS:
    pd.DataFrame(data["groups"][group])
    grp = load_groups(group)
    st.markdown(grp, unsafe_allow_html=True)
