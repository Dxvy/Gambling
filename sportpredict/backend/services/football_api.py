"""
Async wrapper around the API-Football v3 REST API.

Docs: https://www.football-data.org/documentation/quickstart
All endpoints require the RapidAPI key in the request headers.
"""

import os
import logging
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

_API_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
_HEADERS = {
    "X-Auth-Token": _API_KEY,
}


class APIFootballError(Exception):
    """Raised when the API returns an unexpected status or an error payload."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        super().__init__(f"football-data.org error {status_code}: {detail}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get(path: str, params: dict[str, Any] = None) -> Any:
    """
    Make a single GET request and return the full parsed JSON body.

    Unlike the previous wrapper we return the full body (not just body["response"])
    because football-data.org structures vary per endpoint — each normalizer
    below handles its own key extraction.
    """
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
        response = await client.get(url, params=params or {})

    if response.status_code == 429:
        raise APIFootballError(429, "Rate limit reached — wait 60s (free tier: 10 req/min)")

    if response.status_code not in (200, 201):
        raise APIFootballError(response.status_code, response.text[:200])

    return response.json()


# ---------------------------------------------------------------------------
# Normalizers — convert football-data.org shapes into the API-Football shapes
# that features.py already expects. Isolating them here means only this file
# ever needs to change if the upstream API evolves.
# ---------------------------------------------------------------------------

def _normalize_match(match: dict, competition_name: str = "") -> dict:
    """
    Convert a football-data.org match object into the API-Football fixture shape.

    API-Football shape (what features.py expects):
    {
      "fixture": { "id": int, "date": str },
      "teams": {
        "home": { "id": int, "name": str, "winner": bool | None },
        "away": { "id": int, "name": str, "winner": bool | None }
      },
      "goals": { "home": int | None, "away": int | None },
      "league": { "name": str }
    }
    """
    score    = match.get("score", {})
    full     = score.get("fullTime", {})
    home_g   = full.get("home")
    away_g   = full.get("away")

    # Determine winner flags (None = not played yet)
    winner_code = score.get("winner")          # "HOME_TEAM" | "AWAY_TEAM" | "DRAW" | None
    home_winner = True  if winner_code == "HOME_TEAM" else (False if winner_code in ("AWAY_TEAM", "DRAW") else None)
    away_winner = True  if winner_code == "AWAY_TEAM" else (False if winner_code in ("HOME_TEAM", "DRAW") else None)

    return {
        "fixture": {
            "id":   match.get("id"),
            "date": match.get("utcDate"),
        },
        "teams": {
            "home": {
                "id":     match.get("homeTeam", {}).get("id"),
                "name":   match.get("homeTeam", {}).get("name", ""),
                "winner": home_winner,
            },
            "away": {
                "id":     match.get("awayTeam", {}).get("id"),
                "name":   match.get("awayTeam", {}).get("name", ""),
                "winner": away_winner,
            },
        },
        "goals": { "home": home_g, "away": away_g },
        "league": {
            "name": competition_name or match.get("competition", {}).get("name", "")
        },
    }


def _compute_team_stats(team_id: int, matches: list[dict], league_name: str) -> dict:
    """
    Build a synthetic team-stats object from a list of finished matches.

    Mirrors the shape returned by API-Football /teams/statistics so that
    features.py can access: stats["form"], stats["goals"]["for"]["average"]["home"],
    stats["team"]["id"], etc.
    """
    form_chars = []
    home_goals_for:   list[int] = []
    away_goals_for:   list[int] = []
    home_goals_against: list[int] = []
    away_goals_against: list[int] = []
    wins = draws = losses = 0

    for m in matches:
        score   = m.get("score", {})
        full    = score.get("fullTime", {})
        home_g  = full.get("home") or 0
        away_g  = full.get("away") or 0
        winner  = score.get("winner")       # "HOME_TEAM" | "AWAY_TEAM" | "DRAW"

        is_home = m.get("homeTeam", {}).get("id") == team_id

        if is_home:
            home_goals_for.append(home_g)
            home_goals_against.append(away_g)
            if winner == "HOME_TEAM":
                form_chars.append("W"); wins += 1
            elif winner == "AWAY_TEAM":
                form_chars.append("L"); losses += 1
            else:
                form_chars.append("D"); draws += 1
        else:
            away_goals_for.append(away_g)
            away_goals_against.append(home_g)
            if winner == "AWAY_TEAM":
                form_chars.append("W"); wins += 1
            elif winner == "HOME_TEAM":
                form_chars.append("L"); losses += 1
            else:
                form_chars.append("D"); draws += 1

    def avg(lst: list) -> str:
        return f"{sum(lst)/len(lst):.2f}" if lst else "0.00"

    played = wins + draws + losses

    return {
        "team": { "id": team_id },
        "league": { "name": league_name },
        # Form string — last 5 results, most-recent last (same convention as API-Football)
        "form": "".join(form_chars[-5:]),
        "fixtures": {
            "played": { "home": len(home_goals_for), "away": len(away_goals_for), "total": played },
            "wins":   { "home": wins,   "away": wins,   "total": wins   },
            "draws":  { "home": draws,  "away": draws,  "total": draws  },
            "loses":  { "home": losses, "away": losses, "total": losses },
        },
        "goals": {
            "for": {
                "average": {
                    "home":  avg(home_goals_for),
                    "away":  avg(away_goals_for),
                    "total": avg(home_goals_for + away_goals_for),
                }
            },
            "against": {
                "average": {
                    "home":  avg(home_goals_against),
                    "away":  avg(away_goals_against),
                    "total": avg(home_goals_against + away_goals_against),
                }
            },
        },
    }


# ---------------------------------------------------------------------------
# Public API — identical signatures to the previous API-Football wrapper
# (except league_id is now str, e.g. "PL" instead of 39)
# ---------------------------------------------------------------------------

async def get_fixtures(league_id: str, season: int = 2024, next_n: int = 10) -> list[dict]:
    """
    Return the next ``next_n`` upcoming fixtures for a given competition.

    league_id must be a football-data.org competition code, e.g.:
      "PL"  = Premier League       "FL1" = Ligue 1
      "PD"  = La Liga              "BL1" = Bundesliga
      "SA"  = Serie A              "CL"  = Champions League

    Output shape is identical to the old API-Football wrapper so the router
    and any consumers never need to change.
    """
    logger.info("Fetching fixtures — competition=%s season=%d", league_id, season)
    body = await _get(
        f"/competitions/{league_id}/matches",
        params={"status": "SCHEDULED", "season": season},
    )
    matches = body.get("matches", [])[:next_n]
    comp_name = body.get("competition", {}).get("name", "")
    return [_normalize_match(m, comp_name) for m in matches]


async def get_team_stats(team_id: int, league_id: str, season: int = 2024) -> dict:
    """
    Return aggregate statistics for one team in one competition season.

    football-data.org has no direct /teams/statistics endpoint on the free tier,
    so we reconstruct the same shape by fetching the team's finished matches
    and computing form, goals averages, and win/draw/loss totals ourselves.
    """
    logger.info("Fetching team stats — team=%d competition=%s", team_id, league_id)
    body = await _get(
        f"/teams/{team_id}/matches",
        params={
            "competitions": league_id,
            "season":       season,
            "status":       "FINISHED",
            "limit":        38,        # Full season worth of matches
        },
    )
    matches   = body.get("matches", [])
    comp_name = league_id                  # Use code as fallback label
    return _compute_team_stats(team_id, matches, comp_name)


async def get_head_to_head(team1_id: int, team2_id: int, last: int = 10) -> list[dict]:
    """
    Return the last ``last`` head-to-head fixtures between two teams.

    football-data.org provides a direct H2H endpoint under /matches/head2head
    using a match ID as anchor. Since we don't always have one, we fall back to
    fetching team1's recent matches and filtering for team2 as opponent.
    """
    logger.info("Fetching H2H — %d vs %d", team1_id, team2_id)
    body = await _get(
        f"/teams/{team1_id}/matches",
        params={"status": "FINISHED", "limit": 50},
    )
    all_matches = body.get("matches", [])

    # Keep only matches where team2 was the opponent
    h2h = [
        m for m in all_matches
        if m.get("homeTeam", {}).get("id") == team2_id
           or m.get("awayTeam", {}).get("id") == team2_id
    ][:last]

    return [_normalize_match(m) for m in h2h]


async def get_standings(league_id: str, season: int = 2024) -> list[dict]:
    """
    Return the league table for a given competition.

    Output shape mirrors API-Football: a list of row dicts each with
    "team" (id, name), "rank", "points", "goalDifference".
    """
    logger.info("Fetching standings — competition=%s season=%d", league_id, season)
    body = await _get(
        f"/competitions/{league_id}/standings",
        params={"season": season},
    )
    try:
        table = body["standings"][0]["table"]
    except (KeyError, IndexError, TypeError):
        return []

    # Normalize to API-Football row shape
    return [
        {
            "rank":            row.get("position"),
            "team":            { "id": row["team"]["id"], "name": row["team"]["name"] },
            "points":          row.get("points"),
            "goalsDiff":       row.get("goalDifference"),
            "all": {
                "played": row.get("playedGames"),
                "win":    row.get("won"),
                "draw":   row.get("draw"),
                "lose":   row.get("lost"),
            },
        }
        for row in table
    ]


async def get_match_result(
    competition_code: str,
    home_team: str,
    away_team: str,
    match_date: str,
) -> Literal["HOME", "DRAW", "AWAY"] | None:
    """
    Look up the result of a finished match by team name on a given date.

    ``match_date`` is the ISO date(time) string stored on the prediction
    (only the first 10 chars — YYYY-MM-DD — are used to scope the lookup).
    Team names are matched case-insensitively by substring, the same approach
    ``find_match_odds`` uses in odds_api.py, since team names can differ
    slightly between data sources.

    Returns ``None`` if no finished match is found yet (the fixture hasn't
    been played, or the league/date doesn't match).
    """
    date_only = match_date[:10]
    logger.info(
        "Looking up result — competition=%s date=%s %s vs %s",
        competition_code, date_only, home_team, away_team,
    )
    body = await _get(
        f"/competitions/{competition_code}/matches",
        params={"status": "FINISHED", "dateFrom": date_only, "dateTo": date_only},
    )
    matches = body.get("matches", [])

    home_lower = home_team.lower()
    away_lower = away_team.lower()

    for m in matches:
        m_home = m.get("homeTeam", {}).get("name", "").lower()
        m_away = m.get("awayTeam", {}).get("name", "").lower()

        if (home_lower in m_home or m_home in home_lower) and \
           (away_lower in m_away or m_away in away_lower):
            winner = m.get("score", {}).get("winner")
            if winner == "HOME_TEAM":
                return "HOME"
            if winner == "AWAY_TEAM":
                return "AWAY"
            if winner == "DRAW":
                return "DRAW"
            return None

    return None


async def get_team_recent_form(team_id: int, last: int = 5) -> list[dict]:
    """
    Return the ``last`` most recent finished fixtures for a team across all competitions.

    Useful for cross-competition form when per-league data is thin.
    """
    logger.info("Fetching recent form — team=%d last=%d", team_id, last)
    body = await _get(
        f"/teams/{team_id}/matches",
        params={"status": "FINISHED", "limit": last},
    )
    matches = body.get("matches", [])
    return [_normalize_match(m) for m in matches]