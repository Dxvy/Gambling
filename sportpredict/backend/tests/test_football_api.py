"""Tests for services/football_api.py — the rate limiter, TTL cache, the
home/away win-draw-loss parsing bug fix, and season resolution."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import pytest

from services.football_api import (
    _cache_get,
    _cache_set,
    _compute_team_stats,
    _RateLimiter,
    resolve_season,
)


class TestComputeTeamStats:
    """Regression test for the bug where home/away wins-draws-losses were
    combined totals assigned to BOTH venue keys, inflating win rates (a team
    that won 4/6 games total would show 4 wins at home AND 4 wins away,
    instead of splitting e.g. 3 home / 1 away)."""

    def test_splits_wins_draws_losses_by_venue(self):
        team_id = 1
        matches = [
            # Team 1 at home: win
            {"homeTeam": {"id": 1}, "awayTeam": {"id": 2},
             "score": {"fullTime": {"home": 2, "away": 0}, "winner": "HOME_TEAM"}},
            # Team 1 at home: draw
            {"homeTeam": {"id": 1}, "awayTeam": {"id": 3},
             "score": {"fullTime": {"home": 1, "away": 1}, "winner": "DRAW"}},
            # Team 1 away: loss
            {"homeTeam": {"id": 4}, "awayTeam": {"id": 1},
             "score": {"fullTime": {"home": 3, "away": 0}, "winner": "HOME_TEAM"}},
            # Team 1 away: win
            {"homeTeam": {"id": 5}, "awayTeam": {"id": 1},
             "score": {"fullTime": {"home": 0, "away": 2}, "winner": "AWAY_TEAM"}},
        ]
        stats = _compute_team_stats(team_id, matches, "TEST")

        assert stats["fixtures"]["played"] == {"home": 2, "away": 2, "total": 4}
        assert stats["fixtures"]["wins"] == {"home": 1, "away": 1, "total": 2}
        assert stats["fixtures"]["draws"] == {"home": 1, "away": 0, "total": 1}
        assert stats["fixtures"]["loses"] == {"home": 0, "away": 1, "total": 1}

    def test_form_string_is_last_5_results_most_recent_last(self):
        matches = [
            {"homeTeam": {"id": 1}, "awayTeam": {"id": 9},
             "score": {"fullTime": {"home": 1, "away": 0}, "winner": "HOME_TEAM"}},
            {"homeTeam": {"id": 1}, "awayTeam": {"id": 9},
             "score": {"fullTime": {"home": 0, "away": 1}, "winner": "AWAY_TEAM"}},
        ]
        stats = _compute_team_stats(1, matches, "TEST")
        assert stats["form"] == "WL"

    def test_no_matches_returns_zeroed_stats_not_a_crash(self):
        stats = _compute_team_stats(1, [], "TEST")
        assert stats["fixtures"]["played"] == {"home": 0, "away": 0, "total": 0}
        assert stats["goals"]["for"]["average"]["home"] == "0.00"


class TestTTLCache:
    def test_cache_miss_returns_none(self):
        cache: dict = {}
        assert _cache_get(cache, ("a", "b")) is None

    def test_cache_hit_returns_stored_value(self):
        cache: dict = {}
        _cache_set(cache, ("a", "b"), {"x": 1})
        assert _cache_get(cache, ("a", "b")) == {"x": 1}

    def test_expired_entry_is_evicted_and_returns_none(self, monkeypatch):
        cache: dict = {}
        _cache_set(cache, ("a",), "value")

        # Simulate time passing beyond the TTL by monkeypatching time.monotonic
        # used inside football_api's cache helpers.
        import services.football_api as football_api
        real_ttl = football_api._CACHE_TTL_SECONDS
        future = time.monotonic() + real_ttl + 1
        monkeypatch.setattr(football_api.time, "monotonic", lambda: future)

        assert _cache_get(cache, ("a",)) is None
        assert ("a",) not in cache  # eviction actually removes the stale entry


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_burst_up_to_cap_without_waiting(self):
        limiter = _RateLimiter(max_per_minute=5)
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        assert time.monotonic() - start < 0.5

    @pytest.mark.asyncio
    async def test_blocks_the_call_beyond_the_cap(self):
        limiter = _RateLimiter(max_per_minute=2)
        await limiter.acquire()
        await limiter.acquire()

        waited = False

        async def timed_acquire():
            nonlocal waited
            start = time.monotonic()
            await limiter.acquire()
            waited = (time.monotonic() - start) > 0.05

        # Don't actually wait ~60s in the test suite — just confirm acquire()
        # is blocked on the lock/backlog by racing it against a short timeout.
        task = asyncio.create_task(timed_acquire())
        await asyncio.sleep(0.1)
        assert not task.done()  # 3rd call within the same window must still be waiting
        task.cancel()


class TestResolveSeason:
    def test_domestic_league_before_rollover_month_uses_previous_year(self):
        today = datetime(2026, 3, 15)
        assert resolve_season("PL", today=today) == 2025

    def test_domestic_league_after_rollover_month_uses_current_year(self):
        today = datetime(2026, 9, 25)
        assert resolve_season("PL", today=today) == 2026

    def test_fixed_edition_competition_ignores_date(self):
        assert resolve_season("WC", today=datetime(2020, 1, 1)) == 2026
        assert resolve_season("EC", today=datetime(2030, 1, 1)) == 2024
