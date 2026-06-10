"""
The Odds API wrapper — bookmaker odds fetching and value bet detection.

Docs: https://the-odds-api.com/liveapi/guides/v4/

Value bet definition
--------------------
A value bet exists when our model assigns a higher probability to an outcome
than the bookmaker's implied probability (1 / decimal_odds).
An "edge" of 0.05 means we believe the true probability is 5 percentage points
higher than the market price — enough to expect long-run profit at that stake.
"""

from __future__ import annotations

import logging
import os
from typing import Literal

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("ODDS_API_KEY", "")
_BASE_URL = "https://api.the-odds-api.com/v4"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# ---------------------------------------------------------------------------
# Mapping: API-Football league ID → The Odds API sport key
# The Odds API uses string keys like "soccer_epl"; not numeric IDs.
# ---------------------------------------------------------------------------
LEAGUE_TO_ODDS_KEY: dict[int, str] = {
    39:  "soccer_epl",               # England — Premier League
    40:  "soccer_england_efl_champ", # England — Championship
    61:  "soccer_france_ligue_one",  # France  — Ligue 1
    62:  "soccer_france_ligue_deux", # France  — Ligue 2
    78:  "soccer_germany_bundesliga",# Germany — Bundesliga
    79:  "soccer_germany_bundesliga2",
    135: "soccer_italy_serie_a",     # Italy   — Serie A
    136: "soccer_italy_serie_b",
    140: "soccer_spain_la_liga",     # Spain   — La Liga
    141: "soccer_spain_segunda_division",
    2:   "soccer_uefa_champs_league",# UEFA Champions League
    3:   "soccer_uefa_europa_league",
}


class OddsAPIError(Exception):
    """Raised when The Odds API returns an unexpected status or error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        super().__init__(f"Odds API error {status_code}: {detail}")


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

async def _get(path: str, params: dict) -> list | dict:
    """Issue a GET request to the Odds API and return the parsed JSON body."""
    url = f"{_BASE_URL}{path}"
    params["apiKey"] = _API_KEY

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(url, params=params)

    if response.status_code == 422:
        # 422 means the sport key or region is invalid — surface a clear error
        raise OddsAPIError(422, f"Invalid params for {path}: {response.text[:200]}")
    if response.status_code != 200:
        raise OddsAPIError(response.status_code, response.text[:200])

    return response.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_odds(
    sport_key: str,
    regions: str = "eu",
    markets: str = "h2h",
) -> list[dict]:
    """
    Return upcoming match odds for a given sport key and region.

    ``regions`` can be "eu", "uk", "us", "au" (comma-separated for multiple).
    ``markets`` is "h2h" (1X2), "spreads", or "totals".

    Each item in the returned list is a match with a nested list of bookmakers.
    Typical response structure::

        [
          {
            "id": "...",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "bookmakers": [
              {
                "key": "bet365",
                "markets": [
                  {
                    "key": "h2h",
                    "outcomes": [
                      {"name": "Arsenal",  "price": 2.10},
                      {"name": "Chelsea",  "price": 3.40},
                      {"name": "Draw",     "price": 3.20}
                    ]
                  }
                ]
              }
            ]
          }
        ]
    """
    logger.info("Fetching odds — sport=%s regions=%s", sport_key, regions)
    return await _get(
        f"/sports/{sport_key}/odds",
        params={"regions": regions, "markets": markets, "oddsFormat": "decimal"},
    )


async def get_league_odds(league_id: int, regions: str = "eu") -> list[dict]:
    """
    Convenience wrapper: look up the sport key for a league ID and fetch odds.

    Returns an empty list if the league is not mapped to an Odds API key.
    """
    sport_key = LEAGUE_TO_ODDS_KEY.get(league_id)
    if not sport_key:
        logger.warning("No Odds API sport key mapped for league_id=%d", league_id)
        return []
    return await get_odds(sport_key, regions=regions)


def find_match_odds(
    odds_list: list[dict],
    home_team: str,
    away_team: str,
) -> dict | None:
    """
    Search ``odds_list`` for a match whose home/away team names contain
    ``home_team`` and ``away_team`` (case-insensitive substring match).

    Returns the full match odds dict or ``None`` if not found.
    The Odds API team names may differ slightly from API-Football names
    (e.g. "Manchester City" vs "Man City"), so substring matching is safer
    than exact equality.
    """
    home_lower = home_team.lower()
    away_lower = away_team.lower()
    for match in odds_list:
        api_home = match.get("home_team", "").lower()
        api_away = match.get("away_team", "").lower()
        if home_lower in api_home or api_home in home_lower:
            if away_lower in api_away or api_away in away_lower:
                return match
    return None


def extract_best_odds(match_odds: dict, outcome: str) -> float | None:
    """
    Find the highest decimal odds offered by any bookmaker for a given outcome.

    ``outcome`` should be "home", "draw", or "away".
    Returns ``None`` if no matching outcome is found.

    We use the *best* available odds (rather than an average) because that's
    the odds a bettor would actually get, and therefore the correct denominator
    for the value bet edge calculation.
    """
    # Map our outcome label to the name the Odds API uses
    home_name = match_odds.get("home_team", "")
    away_name = match_odds.get("away_team", "")
    outcome_name_map = {
        "home": home_name,
        "draw": "Draw",
        "away": away_name,
    }
    target_name = outcome_name_map.get(outcome.lower(), "")
    if not target_name:
        return None

    best_price: float | None = None
    for bookmaker in match_odds.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for o in market.get("outcomes", []):
                if o.get("name", "").lower() == target_name.lower():
                    price = float(o["price"])
                    if best_price is None or price > best_price:
                        best_price = price

    return best_price


# ---------------------------------------------------------------------------
# Value bet detection
# ---------------------------------------------------------------------------

def calculate_edge(model_prob: float, decimal_odds: float) -> float:
    """
    Return the edge of a bet as a fraction.

    edge = model_probability − implied_probability
           where implied_probability = 1 / decimal_odds

    Positive edge means the model thinks the bet is underpriced by the market.
    A rule of thumb: edge > 0.05 is worth considering.
    """
    if decimal_odds <= 1.0:
        # Odds ≤ 1.0 are invalid (guaranteed loss)
        return -1.0
    implied = 1.0 / decimal_odds
    return model_prob - implied


def detect_value_bet(
    model_prob: float,
    decimal_odds: float,
    threshold: float = 0.05,
) -> bool:
    """
    Return True when the edge exceeds ``threshold``.

    Default threshold of 5 % is a conservative starting point.
    Increase it to reduce false positives at the cost of fewer signals.
    """
    return calculate_edge(model_prob, decimal_odds) > threshold


def annotate_with_value_bets(
    prediction: dict,
    match_odds: dict | None,
    threshold: float = 0.05,
) -> dict:
    """
    Enrich a prediction dict with value bet information.

    Looks at the predicted outcome, finds the best bookmaker odds for that
    outcome, and marks ``is_value_bet = True`` when the edge is positive.
    Also adds ``bookmaker_odds`` and ``edge`` keys to the returned dict.

    If ``match_odds`` is None (odds not available), returns the prediction
    unchanged with ``is_value_bet = False``.
    """
    outcome = prediction.get("prediction", "HOME")  # "HOME" | "DRAW" | "AWAY"
    outcome_key = outcome.lower()  # maps to "home" | "draw" | "away"

    if match_odds is None:
        return {**prediction, "is_value_bet": False, "bookmaker_odds": None, "edge": None}

    best_odds = extract_best_odds(match_odds, outcome_key)
    if best_odds is None:
        return {**prediction, "is_value_bet": False, "bookmaker_odds": None, "edge": None}

    # Convert our probability (0–100) back to a fraction for edge calculation
    model_prob_map = {
        "HOME": prediction.get("home_prob", 0) / 100,
        "DRAW": prediction.get("draw_prob", 0) / 100,
        "AWAY": prediction.get("away_prob", 0) / 100,
    }
    model_prob = model_prob_map.get(outcome, 0.0)
    edge = calculate_edge(model_prob, best_odds)

    return {
        **prediction,
        "is_value_bet":    detect_value_bet(model_prob, best_odds, threshold),
        "bookmaker_odds":  best_odds,
        "edge":            round(edge * 100, 2),  # expressed as percentage
    }
