import glob
import json
import os

import pandas as pd


def get_outcome(match_no: int, fixtures: pd.DataFrame) -> str | None:
    """Returns 'A', 'B', or 'D' (draw). None if scores not yet entered.
    For knockout draws resolved by penalties, returns the penalty winner side."""
    match = fixtures[fixtures["match_no"] == match_no]
    if match.empty:
        return None
    row = match.iloc[0]
    score_a, score_b = row["team_a_score"], row["team_b_score"]
    if pd.isna(score_a) or pd.isna(score_b):
        return None
    if score_a > score_b:
        return "A"
    if score_b > score_a:
        return "B"
    if "penalty_winner" in fixtures.columns:
        pen = row.get("penalty_winner")
        if pen is not None and not pd.isna(pen) and pen in ("A", "B"):
            return pen
    return "D"


def get_match_scores(match_no: int, fixtures: pd.DataFrame) -> tuple[int, int] | None:
    match = fixtures[fixtures["match_no"] == match_no]
    if match.empty:
        return None
    row = match.iloc[0]
    score_a, score_b = row["team_a_score"], row["team_b_score"]
    if pd.isna(score_a) or pd.isna(score_b):
        return None
    return (int(score_a), int(score_b))


def get_sum_goals(match_no: int, fixtures: pd.DataFrame) -> int | None:
    scores = get_match_scores(match_no, fixtures)
    return None if scores is None else scores[0] + scores[1]


def get_goal_diff(match_no: int, fixtures: pd.DataFrame) -> int | None:
    """Signed goal difference from team_a's perspective (3-1 → +2, 1-3 → -2)."""
    scores = get_match_scores(match_no, fixtures)
    return None if scores is None else scores[0] - scores[1]


def calc_points(
    match_no: int, actual: pd.DataFrame, prediction: pd.DataFrame
) -> dict:
    """Returns per-category points for a single match.

    Compares outcomes (A/B/D) rather than team names so prediction CSVs
    don't need team name columns — only match_no, scores, penalty_winner.

    Keys: match_no, winners_picked, scores_predicted, total_goals,
          goal_difference, bonus_points, total
    """
    winners_pts = 0
    score_pts = 0
    goals_pts = 0
    gd_pts = 0

    actual_outcome = get_outcome(match_no, actual)
    predicted_outcome = get_outcome(match_no, prediction)
    if actual_outcome is not None and actual_outcome == predicted_outcome:
        winners_pts = 2

    actual_score = get_match_scores(match_no, actual)
    predicted_score = get_match_scores(match_no, prediction)
    if actual_score is not None and actual_score == predicted_score:
        score_pts = 3

    actual_goals = get_sum_goals(match_no, actual)
    predicted_goals = get_sum_goals(match_no, prediction)
    if actual_goals is not None and actual_goals == predicted_goals:
        goals_pts = 2

    actual_gd = get_goal_diff(match_no, actual)
    predicted_gd = get_goal_diff(match_no, prediction)
    if actual_gd is not None and actual_gd == predicted_gd:
        gd_pts = 1

    return {
        "match_no": match_no,
        "winners_picked": winners_pts,
        "scores_predicted": score_pts,
        "total_goals": goals_pts,
        "goal_difference": gd_pts,
        "bonus_points": 0,
        "total": winners_pts + score_pts + goals_pts + gd_pts,
    }


def calc_bonus_r32(actual: pd.DataFrame, preds: pd.DataFrame) -> float:
    """Awards 0.5 points per team correctly predicted to qualify for the R32.
    Uses actual group stage results to determine real qualifiers, then compares
    against the user's predicted qualifiers derived from their group scores.
    """
    from util import calculate_group_qualifiers, calculate_standings

    group_matches = actual[actual["group"].notna()].copy()
    if group_matches.empty:
        return 0.0

    actual_played = group_matches[
        group_matches["team_a_score"].notna() & group_matches["team_b_score"].notna()
    ]
    if actual_played.empty:
        return 0.0

    actual_by_group = {}
    for group, gdf in actual_played.groupby("group"):
        actual_by_group[group] = calculate_standings(gdf)

    actual_qualifiers = set(calculate_group_qualifiers(actual_by_group).values())
    if not actual_qualifiers:
        return 0.0

    # Overlay user scores on actual team names to get predicted standings
    group_fixtures = group_matches[["match_no", "team_a", "team_b", "group"]].copy()
    pred_with_teams = group_fixtures.merge(
        preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
    )
    pred_played = pred_with_teams[
        pred_with_teams["team_a_score"].notna() & pred_with_teams["team_b_score"].notna()
    ]
    if pred_played.empty:
        return 0.0

    pred_by_group = {}
    for group, gdf in pred_played.groupby("group"):
        pred_by_group[group] = calculate_standings(gdf)

    pred_qualifiers = set(calculate_group_qualifiers(pred_by_group).values())
    correct = len(actual_qualifiers & pred_qualifiers)
    return round(correct * 0.5, 1)


def recalculate_all_points() -> None:
    """Compares every user's predictions against actual results and writes
    per-match breakdowns to points_audit.json and totals to points_table.json.
    Only matches that have actual scores are included.
    """
    actual = pd.read_json("assets/json/match_results.json")
    played = actual[
        actual["team_a_score"].notna() & actual["team_b_score"].notna()
    ]["match_no"].tolist()

    with open("config.yaml", encoding="utf-8") as f:
        import yaml
        config = yaml.safe_load(f)
    table_index = {u["username"]: u["firstname"] for u in config["users"]}

    audit: dict[str, list] = {}
    table: list[dict] = []

    for path in glob.glob("assets/csv_files/predictions/*.csv"):
        username = os.path.splitext(os.path.basename(path))[0]
        if username not in table_index:
            continue

        firstname = table_index[username]

        preds = pd.read_csv(path)
        user_audit = []
        totals = {
            "winners_picked": 0,
            "scores_predicted": 0,
            "total_goals": 0,
            "goal_difference": 0,
            "bonus_points": 0,
        }

        for match_no in played:
            result = calc_points(match_no, actual, preds)
            user_audit.append(result)
            for k in totals:
                totals[k] += result[k]

        bonus = calc_bonus_r32(actual, preds)
        totals["bonus_points"] = bonus
        user_audit.append({
            "match_no": None,
            "winners_picked": 0,
            "scores_predicted": 0,
            "total_goals": 0,
            "goal_difference": 0,
            "bonus_points": bonus,
            "total": bonus,
        })

        audit[username] = user_audit
        table.append({
            "username": username,
            "firstname": firstname,
            **totals,
        })

    with open("assets/json/points_audit.json", "w") as f:
        json.dump(audit, f, indent=2)

    with open("assets/json/points_table.json", "w") as f:
        json.dump(table, f, indent=2)
