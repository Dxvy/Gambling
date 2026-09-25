"""
Build a historical training set for ml/train.py from free football-data.co.uk
CSVs (no API key needed — a different site than football-data.org, so the
10 req/min limit in services/football_api.py does not apply here).

Usage
-----
    python ml/build_training_data.py --out ml/data/historical_matches.csv

For each league+season, matches are walked in chronological order and, for
every match, the exact 13 features in ml/features.py's FEATURE_COLS are
computed from ONLY matches strictly before that date (no lookahead / no
leakage) — mirroring build_match_features()'s semantics so training features
match what services/prediction.py computes at inference time:

  - home_form / away_form: points-per-game ratio over the team's last 5
    results (any venue), 0.5 if no results yet — see form_to_points().
  - home_goals_avg / home_conceded_avg: the home team's average goals
    scored/conceded IN HOME GAMES ONLY, cumulative this league-season
    (0.0 if no home games played yet). away_goals_avg/away_conceded_avg
    are the mirror for away games.
  - home_win_rate / away_win_rate: win rate in home/away games this
    league-season (0.33 default with no games played yet).
  - h2h_home_wins / h2h_goals_avg: from up to the last 10 PRIOR meetings
    between these two teams (pooled across all leagues/seasons processed
    so far, since services/football_api.get_head_to_head() is not
    competition-scoped either) — 0.5 / 2.5 defaults with no prior meetings.

All per-team season counters (form, goals, win rate) reset at the start of
each league+season, matching that get_team_stats() is called with a season
param. H2H history is NOT reset between seasons, matching that
get_head_to_head() pulls a team's last 50 matches with no season filter.

Known approximation: the live get_head_to_head() pulls the home team's last
50 matches across every competition it played (cups included) and keeps the
last 10 vs the opponent from that list, so on the live site H2H can include
cup meetings and the "last 10" is bounded by recency within that 50-match
window. Here we only have domestic league data, so H2H is pooled only from
the leagues/seasons this script downloads — a reasonable but not identical
approximation, called out per the task brief.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `from ml.features import ...`

from ml.features import FEATURE_COLS, form_to_points  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"

# football-data.co.uk league codes -> human label (informational only; the
# app's own competition codes like "FL1"/"PL" never appear in the training
# features, so no mapping to them is needed).
LEAGUES: dict[str, str] = {
    "E0":  "Premier League",
    "E1":  "Championship",
    "F1":  "Ligue 1",
    "D1":  "Bundesliga",
    "I1":  "Serie A",
    "SP1": "La Liga",
}

SEASONS = ["2021", "2122", "2223", "2324", "2425"]

_H2H_LAST_N = 10


def _download_csv(league: str, season: str) -> list[dict] | None:
    url = BASE_URL.format(season=season, league=league)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.info("  %s %s: not available (404) — skipping", league, season)
            return None
        logger.warning("  %s %s: HTTP error %s — skipping", league, season, exc.code)
        return None
    except urllib.error.URLError as exc:
        logger.warning("  %s %s: download failed (%s) — skipping", league, season, exc)
        return None

    reader = csv.DictReader(io.StringIO(raw))
    rows = [r for r in reader if r.get("Date") and r.get("HomeTeam") and r.get("FTR")]
    logger.info("  %s %s: %d matches", league, season, len(rows))
    return rows


def _parse_date(date_str: str):
    from datetime import datetime

    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {date_str!r}")


def _blank_team_stats() -> dict:
    return {
        "home_played": 0, "home_wins": 0, "home_draws": 0, "home_losses": 0,
        "away_played": 0, "away_wins": 0, "away_draws": 0, "away_losses": 0,
        "home_goals_for": 0, "home_goals_against": 0,
        "away_goals_for": 0, "away_goals_against": 0,
        "form": [],  # chronological list of "W"/"D"/"L" across all matches this season
    }


def build_rows() -> list[dict]:
    """Walk every league+season chronologically and emit one feature row per match."""
    rows: list[dict] = []
    # H2H pool is keyed by an unordered team-name pair and persists across every
    # league+season processed (mirrors get_head_to_head() not being season-scoped).
    h2h_pool: dict[frozenset, list[dict]] = defaultdict(list)

    for league, label in LEAGUES.items():
        logger.info("Downloading %s (%s)…", league, label)
        for season in SEASONS:
            matches = _download_csv(league, season)
            time.sleep(1)  # be a decent citizen — this is a free, unauthenticated site
            if not matches:
                continue

            # Parse + sort chronologically within this league+season.
            parsed = []
            for m in matches:
                try:
                    date = _parse_date(m["Date"])
                    fthg, ftag = int(float(m["FTHG"])), int(float(m["FTAG"]))
                except (ValueError, KeyError):
                    continue
                parsed.append((date, m["HomeTeam"], m["AwayTeam"], fthg, ftag, m["FTR"]))
            parsed.sort(key=lambda x: x[0])

            team_stats: dict[str, dict] = defaultdict(_blank_team_stats)

            for _date, home, away, fthg, ftag, ftr in parsed:
                hs, aws = team_stats[home], team_stats[away]

                home_form = form_to_points("".join(hs["form"]))
                away_form = form_to_points("".join(aws["form"]))

                home_goals_avg = hs["home_goals_for"] / hs["home_played"] if hs["home_played"] > 0 else 0.0
                away_goals_avg = aws["away_goals_for"] / aws["away_played"] if aws["away_played"] > 0 else 0.0
                home_conceded_avg = hs["home_goals_against"] / hs["home_played"] if hs["home_played"] > 0 else 0.0
                away_conceded_avg = aws["away_goals_against"] / aws["away_played"] if aws["away_played"] > 0 else 0.0

                home_win_rate = hs["home_wins"] / hs["home_played"] if hs["home_played"] > 0 else 0.33
                away_win_rate = aws["away_wins"] / aws["away_played"] if aws["away_played"] > 0 else 0.33

                pair_key = frozenset({home, away})
                prior_meetings = h2h_pool[pair_key][-_H2H_LAST_N:]
                if prior_meetings:
                    home_wins_in_h2h = sum(
                        1 for pm in prior_meetings if pm["home"] == home and pm["home_won"]
                    )
                    h2h_home_wins = home_wins_in_h2h / len(prior_meetings)
                    h2h_goals_avg = sum(pm["home_goals"] + pm["away_goals"] for pm in prior_meetings) / len(prior_meetings)
                else:
                    h2h_home_wins, h2h_goals_avg = 0.5, 2.5

                row = {
                    "home_form": home_form,
                    "away_form": away_form,
                    "home_goals_avg": home_goals_avg,
                    "away_goals_avg": away_goals_avg,
                    "home_conceded_avg": home_conceded_avg,
                    "away_conceded_avg": away_conceded_avg,
                    "home_win_rate": home_win_rate,
                    "away_win_rate": away_win_rate,
                    "h2h_home_wins": h2h_home_wins,
                    "h2h_goals_avg": h2h_goals_avg,
                    "form_diff": home_form - away_form,
                    "goals_diff": home_goals_avg - away_goals_avg,
                    "conceded_diff": away_conceded_avg - home_conceded_avg,
                    "result": {"H": 0, "D": 1, "A": 2}[ftr],
                }
                assert list(row.keys())[:-1] == FEATURE_COLS, "feature order drifted from ml/features.py"
                rows.append(row)

                # Update running counters AFTER computing this row's features.
                hs["home_played"] += 1
                hs["home_goals_for"] += fthg
                hs["home_goals_against"] += ftag
                aws["away_played"] += 1
                aws["away_goals_for"] += ftag
                aws["away_goals_against"] += fthg

                if ftr == "H":
                    hs["home_wins"] += 1; aws["away_losses"] += 1
                    hs["form"].append("W"); aws["form"].append("L")
                elif ftr == "A":
                    aws["away_wins"] += 1; hs["home_losses"] += 1
                    hs["form"].append("L"); aws["form"].append("W")
                else:
                    hs["home_draws"] += 1; aws["away_draws"] += 1
                    hs["form"].append("D"); aws["form"].append("D")

                h2h_pool[pair_key].append({
                    "home": home, "away": away,
                    "home_goals": fthg, "away_goals": ftag,
                    "home_won": ftr == "H",
                })

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="ml/data/historical_matches.csv")
    args = parser.parse_args()

    rows = build_rows()
    logger.info("Built %d total feature rows", len(rows))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLS + ["result"])
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %s", out_path)


if __name__ == "__main__":
    main()
