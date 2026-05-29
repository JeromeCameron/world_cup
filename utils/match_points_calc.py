def match_winner(match):
    if match.empty:
        return None
    row = match.iloc[0]
    score_a = row["team_a_score"]
    score_b = row["team_b_score"]

    if score_a > score_b:
        return row["team_a"]
    elif score_b > score_a:
        return row["team_b"]
    else:
        return None
