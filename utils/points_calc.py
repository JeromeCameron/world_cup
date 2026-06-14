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


def calc_points(match_no: int, actual: pd.DataFrame, prediction: pd.DataFrame) -> dict:
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
    Only calculated once all group stage matches have results."""
    from util import calculate_group_qualifiers, calculate_standings

    group_matches = actual[actual["group"].notna()].copy()
    if group_matches.empty:
        return 0.0

    # Wait until every group match has a result before awarding the bonus
    all_played = group_matches["team_a_score"].notna() & group_matches["team_b_score"].notna()
    if not all_played.all():
        return 0.0

    actual_played = group_matches

    actual_by_group = {}
    for group, gdf in actual_played.groupby("group"):
        actual_by_group[group] = calculate_standings(gdf)

    actual_qualifiers = set(calculate_group_qualifiers(actual_by_group).values())
    if not actual_qualifiers:
        return 0.0

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


def _knockout_winner_points(
    match_no: int,
    actual: "pd.DataFrame",
    preds: "pd.DataFrame",
    actual_pair: tuple[str, str],
    pred_pair: tuple[str, str],
) -> int:
    """Returns 1 if the user predicted the correct winner but the wrong opponent."""
    actual_outcome = get_outcome(match_no, actual)
    predicted_outcome = get_outcome(match_no, preds)
    if not actual_outcome or not predicted_outcome or actual_outcome in ("D",):
        return 0
    actual_winner = actual_pair[0] if actual_outcome == "A" else actual_pair[1]
    pred_winner = pred_pair[0] if predicted_outcome == "A" else pred_pair[1]
    return 1 if actual_winner == pred_winner else 0


def _resolve_predicted_teams(ms: "pd.DataFrame", preds: "pd.DataFrame") -> dict[int, tuple[str, str]]:
    """Returns {match_no: (predicted_team_a, predicted_team_b)} for all knockout matches,
    resolved from the user's own group stage predictions."""
    from util import (
        build_all_knockout_stages,
        build_prediction_fixtures,
        calculate_group_qualifiers,
        calculate_standings,
    )
    group_fixtures = ms[ms["group"].notna()][["match_no", "team_a", "team_b", "group"]].copy()
    pred_with_teams = group_fixtures.merge(
        preds[["match_no", "team_a_score", "team_b_score"]], on="match_no", how="left"
    )
    standings_by_group = {
        grp: calculate_standings(gdf)
        for grp, gdf in pred_with_teams.groupby("group")
    }
    qualifiers = calculate_group_qualifiers(standings_by_group)
    all_fixtures = build_prediction_fixtures(ms, qualifiers, preds)
    resolved = build_all_knockout_stages(all_fixtures)

    result = {}
    for stage_df in resolved.values():
        for _, row in stage_df.iterrows():
            result[int(row["match_no"])] = (row["team_a"], row["team_b"])
    return result


def recalculate_all_points() -> None:
    """Recalculates points for all users and writes results to the database."""
    import pandas as pd
    from utils.db import get_match_results, get_user_map, get_predictions, save_points

    actual = get_match_results()
    played = actual[
        actual["team_a_score"].notna() & actual["team_b_score"].notna()
    ]["match_no"].tolist()

    ms = pd.read_json("assets/json/matches.json")
    knockout_match_nos = set(ms[ms["stage"] != "group"]["match_no"].tolist())
    actual_teams = {
        int(row["match_no"]): (row["team_a"], row["team_b"])
        for _, row in actual.iterrows()
    }

    table_index = get_user_map()
    audit: dict[str, list] = {}
    table: list[dict] = []

    for username, firstname in table_index.items():
        preds = get_predictions(username)
        predicted_teams = _resolve_predicted_teams(ms, preds)
        user_audit = []
        totals = {
            "winners_picked": 0,
            "scores_predicted": 0,
            "total_goals": 0,
            "goal_difference": 0,
            "bonus_points": 0,
        }

        for match_no in played:
            # For knockout matches, check team identity before scoring
            if match_no in knockout_match_nos:
                pred_pair = predicted_teams.get(match_no)
                actual_pair = actual_teams.get(match_no)
                if pred_pair != actual_pair:
                    partial = _knockout_winner_points(match_no, actual, preds, actual_pair, pred_pair)
                    user_audit.append({
                        "match_no": match_no,
                        "winners_picked": partial, "scores_predicted": 0,
                        "total_goals": 0, "goal_difference": 0,
                        "bonus_points": 0, "total": partial,
                    })
                    totals["winners_picked"] += partial
                    continue

            result = calc_points(match_no, actual, preds)
            user_audit.append(result)
            for k in totals:
                totals[k] += result[k]

        bonus = calc_bonus_r32(actual, preds)
        totals["bonus_points"] = bonus
        user_audit.append({
            "match_no": None,
            "winners_picked": 0, "scores_predicted": 0,
            "total_goals": 0, "goal_difference": 0,
            "bonus_points": bonus, "total": bonus,
        })

        audit[username] = user_audit
        table.append({"username": username, "firstname": firstname, **totals})

    save_points(table, audit)
