import json
import os

import pandas as pd


def generate_predictions_file(username: str) -> None:
    path = f"assets/csv_files/predictions/{username}.csv"
    if os.path.exists(path):
        return
    os.makedirs("assets/csv_files/predictions", exist_ok=True)
    with open("assets/json/matches.json") as f:
        matches = json.load(f)
    rows = sorted(
        [
            {
                "match_no": m["match_no"],
                "team_a_score": None,
                "team_b_score": None,
                "penalty_winner": None,
            }
            for m in matches
        ],
        key=lambda x: x["match_no"],
    )
    pd.DataFrame(rows).to_csv(path, index=False)


def calculate_standings(df: pd.DataFrame) -> pd.DataFrame:
    teams = {}

    for _, row in df.iterrows():
        team_a = row["team_a"]
        team_b = row["team_b"]
        score_a = row["team_a_score"]
        score_b = row["team_b_score"]

        # initialise teams if not seen yet
        for team in [team_a, team_b]:
            if team not in teams:
                teams[team] = {
                    "Team": team,
                    "P": 0,
                    "W": 0,
                    "D": 0,
                    "L": 0,
                    "GF": 0,
                    "GA": 0,
                    "GD": 0,
                    "Pts": 0,
                }

        if pd.isna(score_a) or pd.isna(score_b):
            continue

        # played
        teams[team_a]["P"] += 1
        teams[team_b]["P"] += 1

        # goals
        teams[team_a]["GF"] += score_a
        teams[team_a]["GA"] += score_b
        teams[team_b]["GF"] += score_b
        teams[team_b]["GA"] += score_a

        # result
        if score_a > score_b:
            teams[team_a]["W"] += 1
            teams[team_a]["Pts"] += 3
            teams[team_b]["L"] += 1
        elif score_b > score_a:
            teams[team_b]["W"] += 1
            teams[team_b]["Pts"] += 3
            teams[team_a]["L"] += 1
        else:
            teams[team_a]["D"] += 1
            teams[team_b]["D"] += 1
            teams[team_a]["Pts"] += 1
            teams[team_b]["Pts"] += 1

    standings = pd.DataFrame(teams.values())

    if not standings.empty:
        standings["GF"] = standings["GF"].round(0).astype(int)
        standings["GA"] = standings["GA"].round(0).astype(int)
        standings["GD"] = standings["GF"] - standings["GA"]
        standings = standings.sort_values(
            by=["Pts", "GD", "GF"], ascending=False
        ).reset_index(drop=True)
        standings.index += 1  # start position at 1

    return standings


def load_third_place_mapping() -> dict:
    """
    Attempts to read your local mapping json. If it doesn't exist, fallback
    logic automatically runs your criteria directly without throwing errors.
    """
    try:
        with open("assets/json/third_place_mapping.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def get_third_place_slot_assignment(
    qualifying_groups: list[str], mapping: dict
) -> dict[str, str]:
    key = "-".join(sorted(qualifying_groups))

    # If the file-based lookup exists, respect it.
    if mapping and key in mapping:
        return mapping[key]

    # Algorithmic Fallback Engine: Solves allocations based strictly on your pool rules
    # if the mapping file is absent, missing the key combo, or generated dynamically.
    rules = {
        "1A": ["C", "E", "F", "H", "I"],
        "1B": ["E", "F", "G", "I", "J"],
        "1D": ["B", "E", "F", "I", "J"],
        "1E": ["A", "B", "C", "D", "F"],
        "1G": ["A", "E", "H", "I", "J"],
        "1I": ["C", "D", "F", "G", "H"],
        "1K": ["D", "E", "I", "J", "L"],
        "1L": ["E", "H", "I", "J", "K"],
    }

    assignment = {}
    available_groups = set(qualifying_groups)

    # Run a simple matching loop sorting by strict constraint limits
    sorted_slots = sorted(
        rules.keys(), key=lambda k: len([g for g in rules[k] if g in available_groups])
    )

    for slot in sorted_slots:
        match_found = False
        for choice in rules[slot]:
            if choice in available_groups and choice not in assignment.values():
                assignment[slot] = choice
                match_found = True
                break
        if not match_found:
            # Final fallback sweep allocation
            for choice in available_groups:
                if choice not in assignment.values():
                    assignment[slot] = choice
                    break

    return assignment


def calculate_group_qualifiers(
    standings_by_group: dict[str, pd.DataFrame],
) -> dict[str, str]:
    qualifiers = {}
    third_place_teams = []

    for group, standings in standings_by_group.items():
        if standings.empty or standings["P"].sum() == 0:
            continue
        if len(standings) >= 1:
            qualifiers[f"Group {group} Winners"] = standings.iloc[0]["Team"]
        if len(standings) >= 2:
            qualifiers[f"Group {group} Runners Up"] = standings.iloc[1]["Team"]
        if len(standings) >= 3:
            third_place_teams.append(
                {
                    "group": group,
                    "Team": standings.iloc[2]["Team"],
                    "Pts": standings.iloc[2]["Pts"],
                    "GD": standings.iloc[2]["GD"],
                    "GF": standings.iloc[2]["GF"],
                }
            )

    if not third_place_teams:
        return qualifiers

    third_df = pd.DataFrame(third_place_teams)
    third_df = (
        third_df.sort_values(by=["Pts", "GD", "GF"], ascending=False)
        .head(8)
        .reset_index(drop=True)
    )

    qualifying_groups = third_df["group"].tolist()

    mapping = load_third_place_mapping()
    slot_assignment = get_third_place_slot_assignment(qualifying_groups, mapping)

    for slot, group in slot_assignment.items():
        team_row = third_df[third_df["group"] == group]
        if not team_row.empty:
            qualifiers[f"Group {slot} 3rd Place"] = team_row.iloc[0]["Team"]

    return qualifiers


def build_round_of_32(
    fixtures: pd.DataFrame, qualifiers: dict[str, str]
) -> pd.DataFrame:
    """
    fixtures: the FIFA provided round of 32 dataframe
    qualifiers: dict from calculate_group_qualifiers
    """
    r32 = fixtures.copy()

    r32["team_a"] = r32["team_a"].map(lambda x: qualifiers.get(x, x))
    r32["team_b"] = r32["team_b"].map(lambda x: qualifiers.get(x, x))

    return r32


# --------------------------------------------------------------------


def get_match_winner(match_no: int, fixtures: pd.DataFrame) -> str | None:
    """Returns the winner of a match or None if scores not entered yet.
    For draws in knockout matches, resolves via penalty_winner ('A' or 'B')."""
    match = fixtures[fixtures["match_no"] == match_no]
    if match.empty:
        return None
    row = match.iloc[0]
    score_a = row["team_a_score"]
    score_b = row["team_b_score"]

    if pd.isna(score_a) or pd.isna(score_b):
        return None

    if score_a > score_b:
        return row["team_a"]
    elif score_b > score_a:
        return row["team_b"]

    if "penalty_winner" in fixtures.columns:
        pen = row["penalty_winner"]
        if not pd.isna(pen) and pen in ("A", "B"):
            return row["team_a"] if pen == "A" else row["team_b"]
    return None


def get_match_loser(match_no: int, fixtures: pd.DataFrame) -> str | None:
    """Returns the loser of a match or None if scores not entered yet.
    For draws in knockout matches, resolves via penalty_winner ('A' or 'B')."""
    match = fixtures[fixtures["match_no"] == match_no]
    if match.empty:
        return None
    row = match.iloc[0]
    score_a = row["team_a_score"]
    score_b = row["team_b_score"]

    if pd.isna(score_a) or pd.isna(score_b):
        return None

    if score_a > score_b:
        return row["team_b"]
    elif score_b > score_a:
        return row["team_a"]

    if "penalty_winner" in fixtures.columns:
        pen = row["penalty_winner"]
        if not pd.isna(pen) and pen in ("A", "B"):
            return row["team_b"] if pen == "A" else row["team_a"]
    return None


def resolve_slot(slot: str, fixtures: pd.DataFrame) -> str:
    """
    Resolves a slot like 'Match 74 Winner' or 'Match 101 Loser'
    to an actual team name
    """
    slot = slot.strip()

    # only process slots that start with "Match"
    if not slot.startswith("Match"):
        return slot

    try:
        if "Winner" in slot:
            match_no = int(slot.replace("Match", "").replace("Winner", "").strip())
            result = get_match_winner(match_no, fixtures)
            return result if result else slot

        elif "Loser" in slot:
            match_no = int(slot.replace("Match", "").replace("Loser", "").strip())
            result = get_match_loser(match_no, fixtures)
            return result if result else slot

    except ValueError:
        return slot  # return as-is if parsing fails

    return slot


def build_knockout_stage(
    stage_fixtures: pd.DataFrame, all_fixtures: pd.DataFrame
) -> pd.DataFrame:
    """
    Resolves team names for a knockout stage based on previous results.
    stage_fixtures: the fixtures for the stage to build e.g round of 16
    all_fixtures: the complete fixtures dataframe with all scores
    """
    df = stage_fixtures.copy()
    df["team_a"] = df["team_a"].apply(lambda x: resolve_slot(str(x), all_fixtures))
    df["team_b"] = df["team_b"].apply(lambda x: resolve_slot(str(x), all_fixtures))
    return df


def build_prediction_fixtures(
    ms: pd.DataFrame,
    qualifiers: dict[str, str],
    user_preds: pd.DataFrame,
) -> pd.DataFrame:
    """
    Returns a unified fixtures DataFrame with:
    - R32 team names resolved from group stage qualifiers
    - User prediction scores overlaid for all matches

    This lets build_all_knockout_stages resolve each stage's teams
    from the user's predicted results in prior rounds.
    """
    all_fixtures = ms.copy()
    all_fixtures["penalty_winner"] = None

    r32_resolved = build_round_of_32(
        ms[ms["stage"] == "round_of_32"].copy(), qualifiers
    )

    all_fixtures.set_index("match_no", inplace=True)
    r32_resolved.set_index("match_no", inplace=True)
    all_fixtures.update(r32_resolved[["team_a", "team_b"]])

    score_cols = ["team_a_score", "team_b_score"]
    if "penalty_winner" in user_preds.columns:
        score_cols.append("penalty_winner")
    all_fixtures.update(
        user_preds.drop_duplicates("match_no").set_index("match_no")[score_cols]
    )

    return all_fixtures.reset_index()


def build_all_knockout_stages(all_fixtures: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Builds all knockout stages in order.
    After each stage, resolved team names are written back into the working
    fixtures so subsequent stages can resolve "Match X Winner" correctly.
    Returns a dict of stage name -> resolved fixtures dataframe.
    """
    stages = [
        "round_of_32",
        "round_of_16",
        "quarter_final",
        "semi_final",
        "third_place",
        "final",
    ]

    results = {}
    fixtures = all_fixtures.copy()

    for stage in stages:
        stage_df = fixtures[fixtures["stage"] == stage].copy()
        if not stage_df.empty:
            resolved = build_knockout_stage(stage_df, fixtures)
            results[stage] = resolved
            # Write resolved team names back so the next stage can find winners
            fixtures.set_index("match_no", inplace=True)
            fixtures.update(resolved.set_index("match_no")[["team_a", "team_b"]])
            fixtures.reset_index(inplace=True)

    return results


def render_standings_table(standings: pd.DataFrame, group: str) -> str:
    """Renders a calculated standings DataFrame as a styled HTML table."""
    b = "border: none;"
    th = f"{b} padding: 8px 12px; color: #888; font-weight: 500; text-align: center; font-size: 0.85rem;"
    td_num = f"{b} padding: 10px 12px; text-align: center; font-size: 0.95rem;"
    td_team = f"{b} padding: 10px 12px; font-size: 0.95rem;"
    td_pos = f"{b} padding: 10px 12px; color: #aaa; font-size: 0.9rem; text-align: center; width: 32px;"
    row_style = "border-top: 1px solid #e8e8e8; border-left: none; border-right: none;"

    rows = ""
    for pos, row in standings.iterrows():
        gd = row["GD"]
        gd_color = "color: #2e7d32;" if gd > 0 else "color: #c62828;" if gd < 0 else "color: inherit;"
        rows += f"""
        <tr style="{row_style}">
            <td style="{td_pos}">{pos}</td>
            <td style="{td_team}">{row["Team"]}</td>
            <td style="{td_num}">{row["P"]}</td>
            <td style="{td_num}">{row["W"]}</td>
            <td style="{td_num}">{row["D"]}</td>
            <td style="{td_num}">{row["L"]}</td>
            <td style="{td_num}">{row["GF"]}</td>
            <td style="{td_num}">{row["GA"]}</td>
            <td style="{td_num}; {gd_color}">{gd}</td>
            <td style="{td_num}; font-weight: 700;">{row["Pts"]}</td>
        </tr>"""

    return f"""
    <table style="width:100%; border-collapse: collapse; margin-bottom: 1rem;">
        <thead>
            <tr>
                <th style="border: none; width: 32px;"></th>
                <th style="border: none; text-align: left; padding: 8px 12px; font-size: 1.2rem; font-weight: 600;">Group {group}</th>
                <th style="{th}">P</th>
                <th style="{th}">W</th>
                <th style="{th}">D</th>
                <th style="{th}">L</th>
                <th style="{th}">GF</th>
                <th style="{th}">GA</th>
                <th style="{th}">GD</th>
                <th style="{th}">Pts</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""


def load_groups(group: str) -> str:

    with open("assets/json/groups.json") as f:
        data = json.load(f)

    # Convert to dataframe
    df = pd.DataFrame(data["groups"][group])

    table_rows: str = ""
    counter: int = 1
    for _, row in df.iterrows():
        team_display = row["team"]

        table_rows += (
            f"<tr>"
            f'<td style="border: none;">{counter}</td>'
            f'<td style="border: none;">{team_display}</td>'
            f'<td style="border: none;">{row["P"]}</td>'
            f'<td style="border: none;">{row["W"]}</td>'
            f'<td style="border: none;">{row["D"]}</td>'
            f'<td style="border: none;">{row["L"]}</td>'
            f'<td style="border: none;">{row["GF"]}</td>'
            f'<td style="border: none;">{row["GA"]}</td>'
            f'<td style="border: none;">{row["GD"]}</td>'
            f'<td style="border: none;"><strong>{row["PTS"]}</strong></td>'
            f"</tr>"
        )
        counter += 1

    grp: str = f"""
        <br>
        <table style="width:80%; border: none; border-collapse: collapse;">
            <tr>
                <th style="border: none; border-collapse: collapse;"></th>
                <th style="width:75%; border: none; border-collapse: collapse; font-size: 1.7rem">Group {group}</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">P</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">W</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">D</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">L</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">GF</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">GA</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">GD</th>
                <th style="border: none; border-collapse: collapse; color: #808080;">Pts</th>
            </tr>
            {table_rows}
        </table>
    """
    return grp
