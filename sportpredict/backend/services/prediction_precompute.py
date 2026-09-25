"""
Background job that precomputes predictions for upcoming fixtures and
upserts them into Supabase's ``match_predictions`` table.

The frontend previously never called /predict or /predict/batch at request
time (too slow, and would blow through football-data.org's free-tier rate
limit if many users hit /sports at once). Instead this job walks every
supported league on a schedule and fills the table so the frontend can just
read it with the anon key — see components/sports/MatchList.tsx.

Every football-data.org call made here goes through get_fixtures /
predict_match, which both funnel through services/football_api.py's shared
rate limiter — no extra throttling needed at this layer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from services.fixtures_aggregator import ALL_LEAGUE_CODES
from services.football_api import APIFootballError, get_fixtures, resolve_season
from services.prediction import predict_match
from services.supabase_admin import get_admin_client

logger = logging.getLogger(__name__)

# Only (re)compute a prediction if the existing row is older than this, or
# missing entirely — avoids recomputing fixtures that were already refreshed
# by a recent run.
_FRESHNESS_SECONDS = 6 * 60 * 60

# Only precompute fixtures kicking off within this window — no point spending
# rate-limited API calls on matches weeks away where team form will change.
# Widened from 7 to 14 days: international breaks regularly push a league's
# next matchday out ~15 days, which left a 7-day window computing nothing
# for days at a stretch (observed 2026-09-25 — see incident notes).
_LOOKAHEAD_DAYS = 14

# Fixtures pulled per league per run — mirrors fixtures_aggregator's per-league
# limit to keep a single precompute pass bounded.
_PER_LEAGUE_LIMIT = 5


def _is_fresh(updated_at: str | None) -> bool:
    if not updated_at:
        return False
    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - updated).total_seconds() < _FRESHNESS_SECONDS


async def precompute_predictions() -> int:
    """
    Walk every supported league, predict upcoming fixtures that don't already
    have a fresh prediction, and upsert the results into Supabase.

    Returns the number of predictions written. Failures on one league or one
    fixture are logged and skipped — partial coverage beats none.
    """
    client = get_admin_client()
    if client is None:
        logger.warning("precompute_predictions: Supabase admin client not configured — skipping")
        return 0

    cutoff = datetime.now(timezone.utc) + timedelta(days=_LOOKAHEAD_DAYS)
    total_written = 0

    for league_id in ALL_LEAGUE_CODES:
        try:
            fixtures = await get_fixtures(league_id, next_n=_PER_LEAGUE_LIMIT)
        except APIFootballError as exc:
            logger.warning("precompute_predictions: fixtures fetch failed for %s: %s", league_id, exc)
            continue

        upcoming = []
        for f in fixtures:
            date_str = f.get("fixture", {}).get("date", "")
            try:
                kickoff = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if kickoff <= cutoff:
                upcoming.append(f)

        if not upcoming:
            continue

        fixture_ids = [f["fixture"]["id"] for f in upcoming if f.get("fixture", {}).get("id")]
        fresh_ids: set[int] = set()
        if fixture_ids:
            try:
                existing = (
                    client.table("match_predictions")
                    .select("fixture_id,updated_at")
                    .in_("fixture_id", fixture_ids)
                    .execute()
                )
                fresh_ids = {row["fixture_id"] for row in existing.data if _is_fresh(row.get("updated_at"))}
            except Exception as exc:  # noqa: BLE001
                logger.warning("precompute_predictions: freshness lookup failed for %s: %s", league_id, exc)

        resolved_season = resolve_season(league_id)

        for f in upcoming:
            fixture = f.get("fixture", {})
            fixture_id = fixture.get("id")
            if not fixture_id or fixture_id in fresh_ids:
                continue

            teams = f.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})
            home_id, away_id = home.get("id"), away.get("id")
            if not home_id or not away_id:
                continue

            try:
                result = await predict_match(home_id, away_id, league_id, resolved_season)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "precompute_predictions: prediction failed for fixture %s (%s vs %s): %s",
                    fixture_id, home.get("name"), away.get("name"), exc,
                )
                continue

            row = {
                "fixture_id":     fixture_id,
                "league_id":      league_id,
                "league":         f.get("league", {}).get("name", ""),
                "home_team":      home.get("name", ""),
                "away_team":      away.get("name", ""),
                "kickoff_at":     fixture.get("date"),
                "home_form":      result.get("home_form", ""),
                "away_form":      result.get("away_form", ""),
                "home_prob":      result["home_prob"],
                "draw_prob":      result["draw_prob"],
                "away_prob":      result["away_prob"],
                "prediction":     result["prediction"],
                "confidence":     result["confidence"],
                "is_value_bet":   result.get("is_value_bet", False),
                "bookmaker_odds": result.get("bookmaker_odds"),
                "edge":           result.get("edge"),
                "model_used":     result["model_used"],
                "is_low_quality": result.get("is_low_quality", False),
                "updated_at":     datetime.now(timezone.utc).isoformat(),
            }

            try:
                client.table("match_predictions").upsert(row, on_conflict="fixture_id").execute()
                total_written += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("precompute_predictions: upsert failed for fixture %s: %s", fixture_id, exc)

    logger.info("precompute_predictions: wrote %d predictions", total_written)
    return total_written
