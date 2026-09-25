"""
FastAPI router for sports predictions.

Endpoints
---------
GET  /api/sports/leagues                       List all leagues grouped by country
GET  /api/sports/fixtures                      Upcoming fixtures for a league
GET  /api/sports/predict                       Predict the outcome of one match
GET  /api/sports/predict/batch                 Predict all fixtures in a league
GET  /api/sports/value-bets/{league_id}        Fixtures with value bet detection
POST /api/sports/insight                       AI-generated insight for a prediction
POST /api/sports/reload-model                  Hot-reload the ML model from disk
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.ai_insight import AIInsightError, InsightResponse, generate_match_insight
from services.fixtures_aggregator import get_cached_fixtures
from services.football_api import APIFootballError, get_fixtures, get_standings
from services.job_status import get_status as get_job_status
from services.odds_api import (
    OddsAPIError,
    annotate_with_value_bets,
    find_match_odds,
    get_league_odds,
)
from services.prediction import get_model_status, predict_match, reload_model
from services.football_api import resolve_season  # add alongside the existing football_api imports

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Response models — kept explicit so FastAPI auto-generates clean OpenAPI docs
# ---------------------------------------------------------------------------

class TeamInfo(BaseModel):
    id: int
    name: str


class FixtureResponse(BaseModel):
    fixture_id: int
    home_team: TeamInfo
    away_team: TeamInfo
    league: str
    league_id: str
    date: str
    status: str
    venue: str | None = None


class PredictionResponse(BaseModel):
    fixture_id: int | None = None
    date: str = ""
    home_team: str
    away_team: str
    league_id: str
    home_prob: float
    draw_prob: float
    away_prob: float
    prediction: Literal["HOME", "DRAW", "AWAY"]
    confidence: int
    is_value_bet: bool = False
    bookmaker_odds: float | None = None
    edge: float | None = None           # positive = value; expressed in %
    model_used: str
    is_low_quality: bool = False
    home_form: str = ""
    away_form: str = ""
    features: dict = Field(default_factory=dict, exclude=True)


class ValueBetResponse(BaseModel):
    fixture_id: int | None = None
    home_team: str
    away_team: str
    prediction: Literal["HOME", "DRAW", "AWAY"]
    confidence: int
    home_prob: float
    draw_prob: float
    away_prob: float
    bookmaker_odds: float
    edge: float                         # % edge over implied probability
    model_used: str


class AllFixturesResponse(BaseModel):
    fixtures:   list[FixtureResponse]
    updated_at: str | None = None


class ReloadResponse(BaseModel):
    success: bool
    message: str


class MatchInsightRequest(BaseModel):
    home_team: str
    away_team: str
    league: str
    home_prob: float
    draw_prob: float
    away_prob: float
    prediction: Literal["HOME", "DRAW", "AWAY"]
    confidence: int
    home_form: str = ""
    away_form: str = ""
    is_value_bet: bool = False
    edge: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_fixture(raw: dict) -> FixtureResponse:
    """
    Convert a raw API-Football fixture dict into our clean FixtureResponse.
    Handles missing optional fields gracefully.
    """
    fixture = raw.get("fixture", {})
    teams   = raw.get("teams",   {})
    league  = raw.get("league",  {})
    venue   = fixture.get("venue", {})

    return FixtureResponse(
        fixture_id = fixture.get("id", 0),
        home_team  = TeamInfo(
            id   = teams.get("home", {}).get("id",   0),
            name = teams.get("home", {}).get("name", "Unknown"),
        ),
        away_team  = TeamInfo(
            id   = teams.get("away", {}).get("id",   0),
            name = teams.get("away", {}).get("name", "Unknown"),
        ),
        league     = league.get("name", ""),
        league_id  = league.get("id",   ""),
        date       = fixture.get("date", ""),
        status     = fixture.get("status", {}).get("long", ""),
        venue      = venue.get("name") if isinstance(venue, dict) else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    summary="Backend job & model status — for manual/automated monitoring",
)
async def health() -> dict:
    """
    Report whether the real model is loaded (vs the rule_based fallback) and
    when the background jobs last ran, so "is the prediction pipeline
    actually working?" is a single request instead of grepping Railway logs.
    """
    return {
        "model": get_model_status(),
        "jobs": get_job_status(),
    }


@router.get("/leagues", summary="List all supported leagues grouped by country")
async def list_leagues() -> dict[str, list[dict]]:
    """
    Return the static league registry used by the frontend sidebar.
    No API call is made — data comes from the in-process constants.
    """
    # Imported here to avoid a circular import at module level
    from ml.features import FEATURE_COLS  # noqa: F401 (confirm import works)

    leagues: dict[str, list[dict]] = {
        "France":       [{"id": "FL1",  "name": "Ligue 1"}],
        "England":      [{"id": "PL",   "name": "Premier League"}, {"id": "ELC", "name": "Championship"}],
        "Spain":        [{"id": "PD",   "name": "La Liga"}],
        "Germany":      [{"id": "BL1",  "name": "Bundesliga"}],
        "Italy":        [{"id": "SA",   "name": "Serie A"}],
        "Portugal":     [{"id": "PPL",  "name": "Primeira Liga"}],
        "Netherlands":  [{"id": "DED",  "name": "Eredivisie"}],
        "Brazil":       [{"id": "BSA",  "name": "Série A"}],
        "Europe":       [{"id": "CL",   "name": "Champions League"}, {"id": "EC", "name": "European Championship"}],
        "World":        [{"id": "WC",   "name": "FIFA World Cup"}],
    }
    return leagues


@router.get(
    "/fixtures",
    response_model=list[FixtureResponse],
    summary="Upcoming fixtures for a league",
)
async def fixtures(
        league_id: str = Query(..., description="football-data.org competition code, e.g. PL"),
        season:    int | None = Query(None, description="Season year. Auto-resolved if omitted (handles WC/EC automatically)."),
        next_n:    int = Query(10, ge=1, le=20, description="Number of upcoming fixtures to return"),
) -> list[FixtureResponse]:
    """
    Return the next N scheduled fixtures for a competition.
    Data is fetched live from football-data.org — one request per call.
    """
    try:
        raw_fixtures = await get_fixtures(league_id, season, next_n)
    except APIFootballError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [_parse_fixture(f) for f in raw_fixtures]


@router.get(
    "/fixtures/all",
    response_model=AllFixturesResponse,
    summary="Upcoming fixtures across every supported competition",
)
async def all_fixtures() -> AllFixturesResponse:
    """
    Return the combined upcoming-fixtures list across every competition in
    the /leagues registry, regardless of country.

    Backed by a cache refreshed every 10 minutes in the background (see
    services/fixtures_aggregator.py) rather than fetched live — fetching all
    12 competitions per request would blow through football-data.org's
    free-tier rate limit (10 req/min).
    """
    cache = get_cached_fixtures()
    return AllFixturesResponse(
        fixtures=[_parse_fixture(f) for f in cache["fixtures"]],
        updated_at=cache["updated_at"],
    )


@router.get(
    "/predict",
    response_model=PredictionResponse,
    summary="Predict the outcome of one match",
)
async def predict(
        home_id:   int = Query(..., description="Team ID for the home team"),
        away_id:   int = Query(..., description="Team ID for the away team"),
        league_id: str = Query(..., description="football-data.org competition code"),
        season:    int | None = Query(None, description="Season year. Auto-resolved if omitted."),
        with_odds: bool = Query(False, description="Fetch bookmaker odds and detect value bets"),
        home_name: str = Query("", description="Home team name (required if with_odds=true)"),
        away_name: str = Query("", description="Away team name (required if with_odds=true)"),
) -> PredictionResponse:
    """
    Predict a single match.

    1. Fetches team stats and H2H data concurrently from football-data.org.
    2. Builds the feature vector.
    3. Runs the XGBoost model (or rule-based fallback).
    4. Optionally fetches bookmaker odds and annotates the value bet edge.
    """
    resolved_season = season if season is not None else resolve_season(league_id)

    try:
        result = await predict_match(home_id, away_id, league_id, resolved_season)
    except APIFootballError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if with_odds and home_name and away_name:
        try:
            odds_list   = await get_league_odds(league_id)
            match_odds  = find_match_odds(odds_list, home_name, away_name)
            result      = annotate_with_value_bets(result, match_odds)
        except OddsAPIError as exc:
            logger.warning("Odds API error (non-fatal): %s", exc)

    return PredictionResponse(
        home_team     = home_name or f"Team #{home_id}",
        away_team     = away_name or f"Team #{away_id}",
        league_id     = league_id,
        home_prob     = result["home_prob"],
        draw_prob     = result["draw_prob"],
        away_prob     = result["away_prob"],
        prediction    = result["prediction"],
        confidence    = result["confidence"],
        is_value_bet  = result.get("is_value_bet", False),
        bookmaker_odds= result.get("bookmaker_odds"),
        edge          = result.get("edge"),
        model_used    = result["model_used"],
        is_low_quality= result.get("is_low_quality", False),
        home_form     = result.get("home_form", ""),
        away_form     = result.get("away_form", ""),
    )


@router.get(
    "/predict/batch",
    response_model=list[PredictionResponse],
    summary="Predict all upcoming fixtures in a league",
)
async def predict_batch(
        league_id:  str  = Query(..., description="football-data.org competition code, e.g. PL"),
        season:     int | None = Query(None, description="Season year. Auto-resolved if omitted (handles WC/EC automatically)."),
        next_n:     int  = Query(10, ge=1, le=20),
        with_odds:  bool = Query(False, description="Annotate value bets from bookmaker odds"),
) -> list[PredictionResponse]:
    """
    Fetch upcoming fixtures and predict all of them.

    Fixture fetching and prediction API calls are made concurrently where
    possible.  Failures on individual matches are logged and skipped rather
    than aborting the whole batch.
    """
    resolved_season = season if season is not None else resolve_season(league_id)

    try:
        raw_fixtures = await get_fixtures(league_id, resolved_season, next_n)
    except APIFootballError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not raw_fixtures:
        return []

    # Optionally pre-fetch odds once for the whole league (one API call)
    odds_list: list[dict] = []
    if with_odds:
        try:
            odds_list = await get_league_odds(league_id)
        except OddsAPIError as exc:
            logger.warning("Batch odds fetch failed (non-fatal): %s", exc)

    async def _predict_one(raw: dict) -> PredictionResponse | None:
        fixture   = raw.get("fixture", {})
        teams     = raw.get("teams",   {})
        league    = raw.get("league",  {})
        home_id   = teams.get("home", {}).get("id")
        away_id   = teams.get("away", {}).get("id")
        home_name = teams.get("home", {}).get("name", "")
        away_name = teams.get("away", {}).get("name", "")

        if not home_id or not away_id:
            return None

        try:
            result = await predict_match(home_id, away_id, league_id, resolved_season)
        except (APIFootballError, Exception) as exc:  # noqa: BLE001
            logger.warning("Skipping fixture %s — prediction failed: %s",
                           fixture.get("id"), exc)
            return None

        if with_odds and odds_list:
            match_odds = find_match_odds(odds_list, home_name, away_name)
            result     = annotate_with_value_bets(result, match_odds)

        return PredictionResponse(
            fixture_id    = fixture.get("id"),
            date          = fixture.get("date", ""),
            home_team     = home_name,
            away_team     = away_name,
            league_id     = league.get("id", league_id),
            home_prob     = result["home_prob"],
            draw_prob     = result["draw_prob"],
            away_prob     = result["away_prob"],
            prediction    = result["prediction"],
            confidence    = result["confidence"],
            is_value_bet  = result.get("is_value_bet", False),
            bookmaker_odds= result.get("bookmaker_odds"),
            edge          = result.get("edge"),
            model_used    = result["model_used"],
            is_low_quality= result.get("is_low_quality", False),
            home_form     = result.get("home_form", ""),
            away_form     = result.get("away_form", ""),
        )

    predictions = await asyncio.gather(*[_predict_one(f) for f in raw_fixtures])
    return [p for p in predictions if p is not None]


@router.get(
    "/value-bets/{league_id}",
    response_model=list[ValueBetResponse],
    summary="Return only matches with a positive value bet edge",
)
async def value_bets(
        league_id: str,
        season:    int | None = Query(None, description="Season year. Auto-resolved if omitted (handles WC/EC automatically)."),
        next_n:    int   = Query(10, ge=1, le=20),
        threshold: float = Query(0.05, ge=0.01, le=0.30,
                                 description="Minimum edge (fraction) to qualify as value bet"),
) -> list[ValueBetResponse]:
    """
    Predict upcoming fixtures and return only those with a value bet edge
    above ``threshold``.

    Requires a valid ODDS_API_KEY in the environment — returns an empty list
    if the odds fetch fails.
    """
    resolved_season = season if season is not None else resolve_season(league_id)

    try:
        raw_fixtures = await get_fixtures(league_id, resolved_season, next_n)
    except APIFootballError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not raw_fixtures:
        return []

    try:
        odds_list = await get_league_odds(league_id)
    except OddsAPIError as exc:
        logger.warning("Odds unavailable for value-bets endpoint: %s", exc)
        return []

    results: list[ValueBetResponse] = []

    for raw in raw_fixtures:
        teams     = raw.get("teams",   {})
        fixture   = raw.get("fixture", {})
        home_id   = teams.get("home", {}).get("id")
        away_id   = teams.get("away", {}).get("id")
        home_name = teams.get("home", {}).get("name", "")
        away_name = teams.get("away", {}).get("name", "")

        if not home_id or not away_id:
            continue

        try:
            pred = await predict_match(home_id, away_id, league_id, resolved_season)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Prediction failed for %s vs %s: %s", home_name, away_name, exc)
            continue

        match_odds = find_match_odds(odds_list, home_name, away_name)
        annotated  = annotate_with_value_bets(pred, match_odds, threshold)

        if annotated.get("is_value_bet") and annotated.get("bookmaker_odds") is not None:
            results.append(ValueBetResponse(
                fixture_id     = fixture.get("id"),
                home_team      = home_name,
                away_team      = away_name,
                prediction     = annotated["prediction"],
                confidence     = annotated["confidence"],
                home_prob      = annotated["home_prob"],
                draw_prob      = annotated["draw_prob"],
                away_prob      = annotated["away_prob"],
                bookmaker_odds = annotated["bookmaker_odds"],
                edge           = annotated["edge"],
                model_used     = annotated["model_used"],
            ))

    results.sort(key=lambda x: x.edge, reverse=True)
    return results


@router.post(
    "/insight",
    response_model=InsightResponse,
    summary="Generate an AI insight for a match prediction",
)
async def match_insight(payload: MatchInsightRequest) -> InsightResponse:
    """
    Ask Claude for a short, human-readable take on why the model favors its
    predicted outcome, given the probabilities, form, and value bet info
    already computed by the prediction endpoints.
    """
    try:
        text = await generate_match_insight(**payload.model_dump())
    except AIInsightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return InsightResponse(insight=text)


@router.post(
    "/reload-model",
    response_model=ReloadResponse,
    summary="Hot-reload the ML model from disk without restarting the server",
)
async def reload_model_endpoint() -> ReloadResponse:
    """
    Tell the prediction service to reload its model from MODEL_PATH.
    Call this after running ``python ml/train.py`` to pick up a newly trained model.
    """
    success = reload_model()
    return ReloadResponse(
        success = success,
        message = "Model reloaded successfully." if success
                  else "Model file not found or failed to load — using rule-based fallback.",
    )
