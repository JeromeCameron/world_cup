import altair as alt
import pandas as pd
import streamlit as st

from util import (
    build_all_knockout_stages,
    build_prediction_fixtures,
    calculate_group_qualifiers,
    calculate_standings,
)
from utils.auth import get_user_map, require_login
from utils.db import get_match_results, get_points_audit_for_user, get_points_table, get_predictions

with open("./css/style.css") as css:
    st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

require_login()

# ── Shared data ───────────────────────────────────────────────────────────────
ms = pd.read_json("assets/json/matches.json")
actual = get_match_results()
user_map = get_user_map()
user_options = {firstname: username for username, firstname in user_map.items()}
sorted_players = sorted(user_options.keys())

# ── Helpers ───────────────────────────────────────────────────────────────────
def _resolve_winner(ms: pd.DataFrame, preds: pd.DataFrame) -> str | None:
    if preds.empty:
        return None
    group_fixtures = ms[ms["group"].notna()][["match_no", "team_a", "team_b", "group"]].copy()
    pred_with_teams = group_fixtures.merge(
        preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
    )
    standings_by_group = {
        g: calculate_standings(gdf) for g, gdf in pred_with_teams.groupby("group")
    }
    qualifiers = calculate_group_qualifiers(standings_by_group)
    all_fixtures = build_prediction_fixtures(ms, qualifiers, preds)
    knockout_stages = build_all_knockout_stages(all_fixtures)
    if "final" not in knockout_stages:
        return None
    row = knockout_stages["final"].iloc[0]
    a, b = row.get("team_a_score"), row.get("team_b_score")
    if pd.isna(a) or pd.isna(b):
        return None
    pen = row.get("penalty_winner")
    if a > b:
        return row["team_a"]
    if b > a:
        return row["team_b"]
    if pen in ("A", "B"):
        return row["team_a"] if pen == "A" else row["team_b"]
    return None


def _calc_r32_accuracy(actual: pd.DataFrame, preds: pd.DataFrame, ms: pd.DataFrame):
    group_matches = actual[actual["group"].notna()].copy()
    if group_matches.empty:
        return 0, 0, 0.0
    if not (group_matches["team_a_score"].notna() & group_matches["team_b_score"].notna()).all():
        return 0, 0, 0.0
    actual_qs = set(calculate_group_qualifiers({
        g: calculate_standings(gdf) for g, gdf in group_matches.groupby("group")
    }).values())
    group_fixtures = ms[ms["group"].notna()][["match_no", "team_a", "team_b", "group"]].copy()
    pred_wt = group_fixtures.merge(
        preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
    )
    pred_played = pred_wt[pred_wt["team_a_score"].notna() & pred_wt["team_b_score"].notna()]
    if pred_played.empty:
        return 0, len(actual_qs), 0.0
    pred_qs = set(calculate_group_qualifiers({
        g: calculate_standings(gdf) for g, gdf in pred_played.groupby("group")
    }).values())
    correct = len(actual_qs & pred_qs)
    total = len(actual_qs)
    return correct, total, round(correct / total * 100, 1) if total else 0.0


def _build_audit_df(username: str) -> pd.DataFrame:
    entries = get_points_audit_for_user(username)
    rows = [e for e in entries if e.get("match_no") is not None]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["match_no"] = pd.to_numeric(df["match_no"], errors="coerce")
    return df.merge(ms[["match_no", "stage"]], on="match_no", how="left")


def _player_summary(audit: pd.DataFrame, preds: pd.DataFrame) -> dict:
    if audit.empty:
        return {"n": 0, "winner_pct": 0.0, "score_pct": 0.0, "gd_pct": 0.0, "winner": None}
    n = len(audit)
    return {
        "n": n,
        "winner_pct": round((audit["winners_picked"] > 0).sum() / n * 100, 1),
        "score_pct":  round((audit["scores_predicted"] > 0).sum() / n * 100, 1),
        "gd_pct":     round((audit["goal_difference"] > 0).sum() / n * 100, 1),
        "winner":     _resolve_winner(ms, preds),
    }


@st.cache_data(ttl=300)
def _all_predicted_winners() -> dict[str, str]:
    _ms = pd.read_json("assets/json/matches.json")
    results = {}
    for username, firstname in get_user_map().items():
        w = _resolve_winner(_ms, get_predictions(username))
        if w:
            results[firstname] = w
    return results


def _get_rank(username: str) -> tuple[int, int]:
    """Returns (rank, total_players) using the same sort as the leaderboard."""
    table_data = get_points_table()
    if not table_data:
        return 0, 0
    df = pd.DataFrame(table_data)
    CATS = ["winners_picked", "scores_predicted", "total_goals", "goal_difference", "bonus_points"]
    df["total_points"] = df[CATS].sum(axis=1)
    df = df.sort_values(
        ["total_points", "winners_picked", "scores_predicted", "goal_difference", "total_goals"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    df.index += 1
    row = df[df["username"] == username]
    return (int(row.index[0]), len(df)) if not row.empty else (0, len(df))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 0 — Community Insights (top of page, no dropdown needed)
# ═══════════════════════════════════════════════════════════════════════════════
st.header("📊 Statistics")

st.subheader("🌍 Community Insights")
st.caption("Aggregated across all players.")

all_winners = _all_predicted_winners()
if all_winners:
    vc = pd.Series(list(all_winners.values())).value_counts()
    winners_df = pd.DataFrame({"Team": vc.index.tolist(), "Players": vc.values.tolist()})
    community_bar = (
        alt.Chart(winners_df)
        .mark_bar(cornerRadiusEnd=4, color="#2e7d32")
        .encode(
            x=alt.X("Players:Q", title="No. of players", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("Team:N", sort="-x", title=None),
            tooltip=["Team:N", alt.Tooltip("Players:Q", title="Players picking this team")],
        )
        .properties(height=max(200, len(winners_df) * 55), title="Most Tipped World Cup Winner")
    )
    count_label = community_bar.mark_text(align="left", dx=5, color="#333").encode(text="Players:Q")
    st.altair_chart(community_bar + count_label, use_container_width=True)
else:
    st.info("No predictions resolved yet.")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Player Analysis
# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("Player Analysis")

selected_name = st.selectbox("Select player", options=sorted_players)
selected_username = user_options[selected_name]

preds = get_predictions(selected_username)
audit_df = _build_audit_df(selected_username)
r32_correct, r32_total, r32_pct = _calc_r32_accuracy(actual, preds, ms)
predicted_winner = _resolve_winner(ms, preds)

# Rank + Winner cards
rank, total_players = _get_rank(selected_username)

RANK_STYLES = {
    1: ("linear-gradient(135deg,#f9a825 0%,#f57f17 100%)", "#fff8e1", "#fff"),
    2: ("linear-gradient(135deg,#90a4ae 0%,#546e7a 100%)", "#eceff1", "#fff"),
    3: ("linear-gradient(135deg,#a1887f 0%,#6d4c41 100%)", "#efebe9", "#fff"),
}
RANK_ICONS = {1: "🥇", 2: "🥈", 3: "🥉"}
default_rank_style = ("linear-gradient(135deg,#1a237e 0%,#283593 100%)", "#e8eaf6", "#fff")

rank_bg, _, rank_fg = RANK_STYLES.get(rank, default_rank_style)
rank_icon = RANK_ICONS.get(rank, "")
rank_label = f"{rank_icon} #{rank}" if rank else "—"

rank_col, winner_col = st.columns([1, 2])

CARD_H = "140px"

with rank_col:
    st.markdown(
        f"""<div style="background:{rank_bg};border-radius:14px;padding:1.5rem 1rem;
            margin:1rem 0 1.5rem 0;text-align:center;height:{CARD_H};
            display:flex;flex-direction:column;justify-content:center;">
            <p style="color:rgba(255,255,255,0.75);font-size:0.75rem;margin:0 0 0.3rem 0;
                letter-spacing:0.12em;text-transform:uppercase;font-weight:600;">
                Leaderboard Position
            </p>
            <p style="color:{rank_fg};font-size:3rem;margin:0;font-weight:800;line-height:1;">
                {rank_label}
            </p>
            <p style="color:rgba(255,255,255,0.65);font-size:0.8rem;margin:0.3rem 0 0 0;">
                of {total_players} players
            </p>
        </div>""",
        unsafe_allow_html=True,
    )

with winner_col:
    if predicted_winner:
        st.markdown(
            f"""<div style="background:linear-gradient(135deg,#1b5e20 0%,#2e7d32 100%);
                border-radius:14px;padding:1.5rem 2rem;margin:1rem 0 1.5rem 0;
                text-align:center;height:{CARD_H};
                display:flex;flex-direction:column;justify-content:center;">
                <p style="color:#a5d6a7;font-size:0.8rem;margin:0 0 0.3rem 0;
                    letter-spacing:0.12em;text-transform:uppercase;font-weight:600;">
                    🏆 Predicted World Cup Winner
                </p>
                <p style="color:#fff;font-size:2rem;margin:0;font-weight:700;line-height:1.2;">
                    {predicted_winner}
                </p>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.info("World Cup winner prediction cannot be resolved — predictions may be incomplete.", icon="🏆")

if audit_df.empty:
    st.info("No match results have been entered yet.")
    st.stop()

total_played = len(audit_df)
winner_correct = int((audit_df["winners_picked"] > 0).sum())
score_correct  = int((audit_df["scores_predicted"] > 0).sum())
gd_correct     = int((audit_df["goal_difference"] > 0).sum())
winner_pct = round(winner_correct / total_played * 100, 1)
score_pct  = round(score_correct  / total_played * 100, 1)
gd_pct     = round(gd_correct     / total_played * 100, 1)

# ── Metric cards ──────────────────────────────────────────────────────────────
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Winner Accuracy", f"{winner_pct}%",  help=f"{winner_correct} of {total_played} matches")
c2.metric("Score Accuracy",  f"{score_pct}%",   help=f"{score_correct} of {total_played} matches")
c3.metric("GD Accuracy",     f"{gd_pct}%",      help=f"{gd_correct} of {total_played} matches")
if r32_total > 0:
    c4.metric("R32 Accuracy", f"{r32_pct}%",    help=f"{r32_correct} of {r32_total} teams")
else:
    c4.metric("R32 Accuracy", "—", help="Available once all group matches are played")

# ── Cumulative points over time ───────────────────────────────────────────────
st.divider()
cum_df = audit_df.sort_values("match_no").copy()
cum_df["Cumulative Points"] = cum_df["total"].cumsum()
cum_df["Match"] = cum_df["match_no"].astype(int)

line_chart = (
    alt.Chart(cum_df)
    .mark_line(
        point=alt.OverlayMarkDef(color="#2e7d32", size=50),
        color="#2e7d32",
        strokeWidth=2.5,
    )
    .encode(
        x=alt.X("Match:Q", title="Match No."),
        y=alt.Y("Cumulative Points:Q", title="Points"),
        tooltip=[
            alt.Tooltip("Match:Q", title="Match"),
            alt.Tooltip("Cumulative Points:Q", title="Total Points"),
            alt.Tooltip("total:Q", title="Points this match"),
        ],
    )
    .properties(height=220, title="Cumulative Points Over Time")
)
st.altair_chart(line_chart, use_container_width=True)

# ── Overall accuracy bar chart ────────────────────────────────────────────────
overview_df = pd.DataFrame({
    "Category": ["Winner", "Exact Score", "Goal Difference"],
    "Accuracy": [winner_pct, score_pct, gd_pct],
    "Correct":  [winner_correct, score_correct, gd_correct],
    "Total":    [total_played,   total_played,   total_played],
})
acc_bar = (
    alt.Chart(overview_df)
    .mark_bar(cornerRadiusEnd=5)
    .encode(
        x=alt.X("Accuracy:Q", scale=alt.Scale(domain=[0, 100]), title="Accuracy (%)"),
        y=alt.Y("Category:N", sort="-x", title=None),
        color=alt.Color("Accuracy:Q", scale=alt.Scale(scheme="greens", domain=[0, 100]), legend=None),
        tooltip=[
            alt.Tooltip("Category:N"),
            alt.Tooltip("Correct:Q",  title="Correct"),
            alt.Tooltip("Total:Q",    title="Played"),
            alt.Tooltip("Accuracy:Q", title="Accuracy (%)", format=".1f"),
        ],
    )
    .properties(height=220, title="Overall Match Prediction Accuracy")
)
acc_label = acc_bar.mark_text(align="left", dx=6, color="#444", fontSize=13).encode(
    text=alt.Text("Accuracy:Q", format=".1f")
)
st.altair_chart(acc_bar + acc_label, use_container_width=True)

# ── Accuracy by stage ─────────────────────────────────────────────────────────
STAGE_ORDER = {
    "group": "Group", "round_of_32": "R32", "round_of_16": "R16",
    "quarter_final": "QF", "semi_final": "SF", "third_place": "3rd", "final": "Final",
}
stage_rows = []
for sk, sl in STAGE_ORDER.items():
    chunk = audit_df[audit_df["stage"] == sk]
    if chunk.empty:
        continue
    n = len(chunk)
    stage_rows.append({
        "Stage":    sl,
        "Winner %": round((chunk["winners_picked"] > 0).sum() / n * 100, 1),
        "Score %":  round((chunk["scores_predicted"] > 0).sum() / n * 100, 1),
        "GD %":     round((chunk["goal_difference"] > 0).sum() / n * 100, 1),
        "Played":   n,
    })
if stage_rows:
    stage_df = pd.DataFrame(stage_rows)
    label_order = [v for v in STAGE_ORDER.values() if v in stage_df["Stage"].values]
    melted = stage_df.melt(
        id_vars=["Stage", "Played"],
        value_vars=["Winner %", "Score %", "GD %"],
        var_name="Metric", value_name="Accuracy",
    )
    stage_chart = (
        alt.Chart(melted)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Stage:N", sort=label_order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Accuracy:Q", scale=alt.Scale(domain=[0, 100]), title="Accuracy (%)"),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(
                    domain=["Winner %", "Score %", "GD %"],
                    range=["#2e7d32", "#66bb6a", "#a5d6a7"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            xOffset=alt.XOffset("Metric:N", sort=["Winner %", "Score %", "GD %"]),
            tooltip=[
                alt.Tooltip("Stage:N"),
                alt.Tooltip("Metric:N"),
                alt.Tooltip("Accuracy:Q", title="Accuracy (%)", format=".1f"),
                alt.Tooltip("Played:Q",   title="Matches played"),
            ],
        )
        .properties(height=280, title="Accuracy by Tournament Stage")
    )
    st.altair_chart(stage_chart, use_container_width=True)

# ── Score predicted vs actual (scatter, one point per team per match) ─────────
played_actual = actual[
    actual["team_a_score"].notna() & actual["team_b_score"].notna()
].copy()
pred_scores = preds[["match_no", "team_a_score", "team_b_score"]].rename(
    columns={"team_a_score": "pred_a", "team_b_score": "pred_b"}
)
merged = played_actual.merge(pred_scores, on="match_no", how="inner").dropna(subset=["pred_a", "pred_b"])

# Two rows per match: one for each team
score_rows = []
for _, row in merged.iterrows():
    a_a, a_b = int(row["team_a_score"]), int(row["team_b_score"])
    p_a, p_b = int(row["pred_a"]), int(row["pred_b"])
    actual_score  = f"{a_a} - {a_b}"
    pred_score    = f"{p_a} - {p_b}"
    label = f"{row['team_a']} vs {row['team_b']}"
    score_rows.append({"Team": row["team_a"], "actual": a_a, "predicted": p_a, "match": label, "Actual Score": actual_score, "Predicted Score": pred_score})
    score_rows.append({"Team": row["team_b"], "actual": a_b, "predicted": p_b, "match": label, "Actual Score": actual_score, "Predicted Score": pred_score})

if score_rows:
    score_scatter_df = pd.DataFrame(score_rows)
    max_s = int(max(score_scatter_df["actual"].max(), score_scatter_df["predicted"].max())) + 1
    ref_df = pd.DataFrame({"x": [0, max_s], "y": [0, max_s]})
    ref_line = (
        alt.Chart(ref_df)
        .mark_line(strokeDash=[5, 5], color="#ccc", strokeWidth=1.5)
        .encode(x=alt.X("x:Q"), y=alt.Y("y:Q"))
    )
    scatter = (
        alt.Chart(score_scatter_df)
        .mark_circle(size=70, opacity=0.65, color="#2e7d32")
        .encode(
            x=alt.X("actual:Q",    title="Actual Goals Scored",    scale=alt.Scale(domain=[0, max_s])),
            y=alt.Y("predicted:Q", title="Predicted Goals Scored", scale=alt.Scale(domain=[0, max_s])),
            tooltip=[
                alt.Tooltip("match:N",           title="Match"),
                alt.Tooltip("Team:N",            title="Team"),
                alt.Tooltip("Actual Score:N",    title="Actual Score"),
                alt.Tooltip("Predicted Score:N", title="Predicted Score"),
            ],
        )
        .properties(height=280, title="Score Predicted vs Actual  ·  points on the diagonal = exact prediction")
    )
    st.altair_chart(ref_line + scatter, use_container_width=True)

# ── Best & worst matches ───────────────────────────────────────────────────────
st.divider()
st.subheader("Best & Worst Matches")

actual_names = actual[["match_no", "team_a", "team_b"]].copy()
audit_named = audit_df.merge(actual_names, on="match_no", how="left")
audit_named["match_label"] = audit_named["team_a"].fillna("") + " vs " + audit_named["team_b"].fillna("")

top3 = audit_named.nlargest(3, "total")[
    ["match_label", "stage", "winners_picked", "scores_predicted", "total_goals", "goal_difference", "total"]
]
zero_count  = int((audit_df["total"] == 0).sum())
bottom_sample = audit_named[audit_named["total"] == 0][["match_label", "stage"]].head(5)

st.markdown("**🌟 Best Matches**")
if top3.empty or top3["total"].max() == 0:
    st.caption("No points scored yet.")
else:
    st.dataframe(
        top3,
        hide_index=True,
        use_container_width=True,
        column_config={
            "match_label":      st.column_config.TextColumn(label="Match"),
            "stage":            st.column_config.TextColumn(label="Stage"),
            "winners_picked":   st.column_config.NumberColumn(label="W"),
            "scores_predicted": st.column_config.NumberColumn(label="S"),
            "total_goals":      st.column_config.NumberColumn(label="Goals"),
            "goal_difference":  st.column_config.NumberColumn(label="GD"),
            "total":            st.column_config.NumberColumn(label="Pts"),
        },
    )

st.markdown("**😬 Zero-Point Matches**")
st.caption(
    f"{zero_count} of {total_played} matches scored 0 pts "
    f"({round(zero_count / total_played * 100, 1)}%)"
)
if not bottom_sample.empty:
    st.dataframe(
        bottom_sample,
        hide_index=True,
        use_container_width=True,
        column_config={
            "match_label": st.column_config.TextColumn(label="Match"),
            "stage":       st.column_config.TextColumn(label="Stage"),
        },
    )

# ── R32 detail table ──────────────────────────────────────────────────────────
if r32_total > 0:
    st.divider()
    st.subheader("R32 Qualification Predictions")
    group_matches = actual[actual["group"].notna()].copy()
    group_fixtures = ms[ms["group"].notna()][["match_no", "team_a", "team_b", "group"]].copy()
    pred_wt = group_fixtures.merge(
        preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
    )
    actual_qs = set(calculate_group_qualifiers({
        g: calculate_standings(gdf) for g, gdf in group_matches.groupby("group")
    }).values())
    pred_qs = set(calculate_group_qualifiers({
        g: calculate_standings(gdf) for g, gdf in pred_wt.groupby("group")
    }).values())
    r32_rows = [
        {
            "Team":      team,
            "Predicted": "✅" if team in pred_qs  else "❌",
            "Qualified": "✅" if team in actual_qs else "❌",
            "Result":    "✓ Correct" if (team in pred_qs) == (team in actual_qs) else "✗ Wrong",
        }
        for team in sorted(actual_qs | pred_qs)
    ]
    r32_display = pd.DataFrame(r32_rows).sort_values(["Qualified", "Team"], ascending=[False, True])

    def _r32_style(row):
        if row["Result"] == "✓ Correct":
            return ["color:#2e7d32;font-weight:600"] * len(row)
        return ["color:#c62828"] * len(row)

    st.dataframe(
        r32_display.style.apply(_r32_style, axis=1),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Team":      st.column_config.TextColumn(label="Team"),
            "Predicted": st.column_config.TextColumn(label="Predicted to Qualify"),
            "Qualified": st.column_config.TextColumn(label="Actually Qualified"),
            "Result":    st.column_config.TextColumn(label="Result"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Head-to-Head
# ═══════════════════════════════════════════════════════════════════════════════
st.divider()
with st.expander("⚔️ Head-to-Head Comparison", expanded=False):
    h2h_c1, h2h_c2 = st.columns(2)
    with h2h_c1:
        p1_name = st.selectbox("Player 1", options=sorted_players, key="h2h_p1")
    with h2h_c2:
        p2_default = min(1, len(sorted_players) - 1)
        p2_name = st.selectbox("Player 2", options=sorted_players, key="h2h_p2", index=p2_default)

    if p1_name == p2_name:
        st.info("Select two different players to compare.")
    else:
        p1_audit  = _build_audit_df(user_options[p1_name])
        p2_audit  = _build_audit_df(user_options[p2_name])
        p1_preds  = get_predictions(user_options[p1_name])
        p2_preds  = get_predictions(user_options[p2_name])
        s1 = _player_summary(p1_audit, p1_preds)
        s2 = _player_summary(p2_audit, p2_preds)

        # Predicted winner cards
        wcard_cols = st.columns(2)
        for col, name, s in zip(wcard_cols, [p1_name, p2_name], [s1, s2]):
            w = s["winner"] or "—"
            with col:
                st.markdown(
                    f"""<div style="background:#f1f8e9;border-radius:10px;padding:1rem;
                        text-align:center;border:1px solid #c5e1a5;margin-bottom:0.75rem;">
                        <p style="color:#558b2f;font-size:0.75rem;margin:0 0 0.25rem;
                            text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">
                            🏆 {name}'s Pick
                        </p>
                        <p style="font-size:1.4rem;margin:0;font-weight:700;">{w}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

        # Comparison bar chart
        h2h_df = pd.DataFrame([
            {"Metric": m, "Player": n, "Accuracy": v}
            for n, s in [(p1_name, s1), (p2_name, s2)]
            for m, v in [("Winner %", s["winner_pct"]), ("Score %", s["score_pct"]), ("GD %", s["gd_pct"])]
        ])
        h2h_chart = (
            alt.Chart(h2h_df)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Metric:N", title=None, axis=alt.Axis(labelAngle=0),
                        sort=["Winner %", "Score %", "GD %"]),
                y=alt.Y("Accuracy:Q", scale=alt.Scale(domain=[0, 100]), title="Accuracy (%)"),
                color=alt.Color(
                    "Player:N",
                    scale=alt.Scale(range=["#2e7d32", "#81c784"]),
                    legend=alt.Legend(title=None, orient="top"),
                ),
                xOffset=alt.XOffset("Player:N", sort=[p1_name, p2_name]),
                tooltip=[
                    alt.Tooltip("Player:N"),
                    alt.Tooltip("Metric:N"),
                    alt.Tooltip("Accuracy:Q", title="Accuracy (%)", format=".1f"),
                ],
            )
            .properties(height=260, title=f"{p1_name} vs {p2_name}")
        )
        st.altair_chart(h2h_chart, use_container_width=True)
