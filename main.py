import numpy as np
from scipy.stats import norm
from espn_api.football import League
from datetime import datetime
from collections import defaultdict
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import requests


app = FastAPI(title="Fantasy")

@app.get("/league_info", response_class=PlainTextResponse)
def league_info():
    # establish league connection via ESPN api
    LEAGUE_ID = 1347842310
    YEAR = 2026
    START_DATE = "9-9-2026"
    WEEK = week_number(START_DATE)
    SEASON = 2026

    league = League(league_id=LEAGUE_ID, year=YEAR)

    output = []

    # get league data
    data = get_league_data(league, WEEK)

    # print data
    output.append(print_league_standings(league, data))
    output.append("")
    output.append(print_league_scores(data))
    output.append("")
    output.append(print_projected_league_standings(league, data))
    output.append("")
    output.append(print_median_summary(data))
    output.append("")
    output.append(get_rankings(WEEK, SEASON))
    output.append("")

    return "\n".join(output)

def get_league_data(league, week):

    # get data from ESPN
    box_scores = league.box_scores(week)
    standings = league.standings()

    # initialize data
    names = []
    scores = []
    projections = []
    wins = []
    losses = []

    # get team names, scores, and projected scores
    for match in box_scores:
        for i in range(0, 2):
            if i == 0:
                names.append(match.home_team.team_name)
                scores.append(round(match.home_score, 2))
                projections.append(round(match.home_projected, 2))
            else:
                names.append(match.away_team.team_name)
                scores.append(round(match.away_score, 2))
                projections.append(round(match.away_projected, 2))


    # get number of wins and losses for each team
    for name in names:
        for team in standings:
            if team.team_name == name:
                wins.append(team.wins)
                losses.append(team.losses)

    # get projected wins and losses
    proj_wins, proj_losses = simulate_week(projections, wins, losses)

    # combine data
    data = [list(el) for el in zip(names, scores, projections, wins, losses, proj_wins, proj_losses)]

    return data

def simulate_week(projections, wins, losses):

    proj_wins = [0] * len(projections)
    proj_losses = [0] * len(projections)

    # get scoring median
    proj_med = np.median(projections)

    # iterate through each team
    for i in range(0, len(projections), 2):

        # check head-to-head
        if projections[i] > projections[i + 1]:
            proj_wins[i] += 1
            proj_losses[i+1] += 1
        else:
            proj_wins[i+1] += 1
            proj_losses[i] += 1

        # check against the median
        if projections[i] > proj_med:
            proj_wins[i] += 1
        else:
            proj_losses[i] += 1

        if projections[i+1] > proj_med:
            proj_wins[i+1] += 1
        else:
            proj_losses[i+1] += 1

    wins = [x + y for x, y in zip(wins, proj_wins)]
    losses = [x + y for x, y in zip(losses, proj_losses)]

    return wins, losses

def print_league_scores(data):

    home_teams = [sublist[0] for sublist in data[::2]]
    away_teams = [sublist[0] for sublist in data[1::2]]

    # find maximum width needed for both columns
    max_left = max(len(el) for el in home_teams)
    max_right = max(len(el) for el in away_teams)

    # print data
    output = []
    output.append("----------Projected Scores-----------")

    for i in range(0, len(data), 2):
        output.append(f"{str(data[i][0]):>{max_left}}{" | "}{str(data[i+1][0]):<{max_right}}")
        output.append(f"{str(data[i][2]):>{max_left}}{" | "}{str(data[i+1][2]):<{max_right}}")

    output.append("")
    output.append("Projected Median Score: " + str(round(np.median([row[2] for row in data]), 2)))
    output.append("")

    output.append("-----------Actual Scores------------")

    for i in range(0, len(data), 2):
        output.append(f"{str(data[i][0]):>{max_left}}{" | "}{str(data[i+1][0]):<{max_right}}")
        output.append(f"{str(data[i][1]):>{max_left}}{" | "}{str(data[i+1][1]):<{max_right}}")

    output.append("")
    output.append("Actual Median Score: " + str(round(np.median([row[1] for row in data]), 2)))
    output.append("")

    return "\n".join(output)

def print_league_standings(league, data):

    # sort by number of wins
    data = sorted(data, key=lambda x: x[3], reverse=True)

    output = []
    # formatting
    title = f"--- {league.settings.name} Standings ---"
    output.append(title)
    t_len = len(title)

    # print data
    for i, team in enumerate(data):
        length = t_len - len(team[0])
        win_loss = "(" + str(team[3]) + "-" + str(team[4]) + ")"
        output.append(f"{str(i + 1)}. {team[0]}{win_loss:>{length}}")

    return "\n".join(output)

def print_projected_league_standings(league, data):

    # sort by number of projected wins
    data = sorted(data, key=lambda x: x[5], reverse=True)

    output = []
    # formatting
    title = f"--- Projected League Standings ---"
    output.append(title)
    t_len = len(title)

    # print data
    for i, team in enumerate(data):
        length = t_len - len(team[0])
        win_loss = "(" + str(team[5]) + "-" + str(team[6]) + ")"
        output.append(f"{str(i + 1)}. {team[0]}{win_loss:>{length}}")

    return "\n".join(output)

def print_median_summary(data):

    # sort by projected score
    data = sorted(data, key=lambda x: x[2], reverse=True)

    # formatting
    output = []

    title = f"-------- Projected Scoring --------"
    output.append(title)
    t_len = len(title)

    # print data
    for i, team in enumerate(data):
        length = t_len - len(team[0])
        proj = "(" + str(team[2]) + ")"
        output.append(f"{str(i + 1)}. {team[0]}{proj:>{length}}")

        if i == 4:
            output.append("--- Median ---")

    return "\n".join(output)

def get_rankings(WEEK, SEASON):
    # 1. Fetch current NFL state (optional auto-week check)
    host = "https://api." + "sleeper.app"

    # 2. Fetch weekly stat projections for QB, RB, WR, TE
    proj_path = f"/projections/nfl/{SEASON}/{WEEK}"

    params = [
        ("season_type", "regular"),
        ("position[]", "QB"),
        ("position[]", "RB"),
        ("position[]", "WR"),
        ("position[]", "TE"),
        ("order_by", "pts_ppr")
    ]

    resp = requests.get(host + proj_path, params=params)
    if resp.status_code != 200:
        print(f"Sleeper API Error {resp.status_code}: {resp.text}")
        return

    data = resp.json()
    rows = []

    for item in data:
        player = item.get("player", {})
        stats = item.get("stats", {})

        full_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        pos = player.get("position")

        # Calculate custom Full-PPR points directly from projected stats
        proj_ppr = (
            stats.get("pass_yd", 0) * 0.04 +
            stats.get("pass_td", 0) * 4.0 +
            stats.get("pass_int", 0) * -2.0 +
            stats.get("rush_yd", 0) * 0.1 +
            stats.get("rush_td", 0) * 6.0 +
            stats.get("rec_yd", 0) * 0.1 +
            stats.get("rec", 0) * 1.0 +
            stats.get("rec_td", 0) * 6.0 +
            stats.get("fum_lost", 0) * -2.0
        )

        if proj_ppr > 0:
            rows.append({
                "player_name": full_name,
                "position": pos,
                "proj_ppr": round(proj_ppr, 2)
            })

    df = pd.DataFrame(rows)
    output = []

    for pos in ["QB", "RB", "WR", "TE"]:
        output.append(f"\n------- {pos} PROJECTIONS (WEEK {WEEK}) -------")

        top_pos = df[df["position"] == pos].sort_values(by="proj_ppr", ascending=False).head(20)

        for rank, row in enumerate(top_pos.itertuples(), start=1):

            output.append(f"{rank:>2}. {row.player_name} {row.proj_ppr:.2f}")

    return "\n".join(output)

def week_number(date_string, date_format="%m-%d-%Y"):

    # NFL start date
    begin_date = datetime.strptime(date_string, date_format)

    today = datetime.now()

    delta = today - begin_date

    weeks = delta.days / 7

    return int(weeks) + 1



if __name__ == "__home__":
    home()
