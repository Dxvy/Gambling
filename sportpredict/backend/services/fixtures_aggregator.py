"""
Cross-league fixture aggregation for the "All Leagues" view.

football-data.org's free tier allows only 10 requests/minute, so fetching
all competitions on every request (or concurrently) would blow through the
limit immediately — the same failure mode already hit once in predict/batch
(see commit 41d396e). Instead, a background job refreshes an in-process
cache periodically (see main.py's scheduler), spacing calls out the same
way services/results_resolver.py already does, and requests just read the
cache — no user request ever triggers a live football-data.org call here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from services.football_api import APIFootballError, get_fixtures

logger = logging.getLogger(__name__)

# Every competition code exposed in the /api/sports/leagues registry.
ALL_LEAGUE_CODES: list[str] = [
    "FL1", "PL", "ELC", "PD", "BL1", "SA", "PPL", "DED", "BSA", "CL", "EC", "WC",
]

# Matches football-data.org's free-tier limit of 10 requests/minute.
_REQUEST_DELAY_SECONDS = 6

# How many upcoming fixtures to pull per competition for the combined view.
_PER_LEAGUE_LIMIT = 5

_cache: dict = {"fixtures": [], "updated_at": None}


def get_cached_fixtures() -> dict:
    """Return the last-refreshed combined fixture list, oldest match first."""
    return _cache


async def refresh_all_fixtures() -> None:
    """
    Fetch upcoming fixtures for every competition, one at a time with a
    rate-limit-safe delay between calls, and replace the cache.

    A failure on one competition (rate limit, upstream error) is logged and
    skipped rather than aborting the whole refresh — partial data beats none.
    """
    combined: list[dict] = []

    for i, code in enumerate(ALL_LEAGUE_CODES):
        if i > 0:
            await asyncio.sleep(_REQUEST_DELAY_SECONDS)
        try:
            combined.extend(await get_fixtures(code, next_n=_PER_LEAGUE_LIMIT))
        except APIFootballError as exc:
            logger.warning("Skipping %s in all-fixtures refresh: %s", code, exc)

    combined.sort(key=lambda f: f.get("fixture", {}).get("date") or "")

    _cache["fixtures"] = combined
    _cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Refreshed all-fixtures cache — %d fixtures across %d competitions",
                len(combined), len(ALL_LEAGUE_CODES))
