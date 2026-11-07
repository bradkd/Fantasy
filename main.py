import numpy as np
from scipy.stats import norm
from espn_api.football import League
from datetime import datetime
from collections import defaultdict
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Fantasy")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def league_info(request: Request):
    # establish league connection via ESPN api
    LEAGUE_ID = 1347842310
    YEAR = 2026
    START_DATE = "9-9-2026"
    WEEK = week_number(START_DATE)

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

    #output = "\n".join(output)

    return templates.TemplateResponse(request=request, name="dashboard.html",context={"request": request, "log_entries": output})

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


def get_position_summary(league, week):

    # dictionary to hold scores
    manager_scores = defaultdict(lambda: defaultdict(float))

    # iterate through all previous weeks
    for week in range(0, 18):

        # iterate through each matchup for the given week
        boxscores = league.box_scores(week)
        for match in boxscores:

            # both home and away teams
            for team in [match.home_team, match.away_team]:

                # get player scores in the lineup for this team
                team_name = team.team_name
                lineup = (match.home_lineup if team == match.home_team else match.away_lineup)

                for player in lineup:

                    # exclude bench slots
                    if player.slot_position == 'BE':
                        continue

                    pos = player.position
                    points = player.points
                    manager_scores[team_name][pos] += points

    # convert to dataframe
    df = pd.DataFrame(manager_scores).fillna(0).T
    df['Total'] = df.sum(axis=1)
    df = df.sort_values(by='Total', ascending=False)

    return df

def week_number(date_string, date_format="%m-%d-%Y"):

    # NFL start date
    begin_date = datetime.strptime(date_string, date_format)

    today = datetime.now()

    delta = today - begin_date

    weeks = delta.days / 7

    return int(weeks) + 1



if __name__ == "__home__":
    home()

