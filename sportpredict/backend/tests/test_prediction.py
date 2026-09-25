"""Tests for services/prediction.py — the low-quality fallback path added
after tracing why predict/batch showed identical probabilities for
different matches (root cause: the rule-based fallback's 3-bucket step
function, not a data bug, but the low-quality flag is what makes future
data-fetch failures visible instead of silently defaulting features)."""

from __future__ import annotations

import pytest

import services.prediction as prediction
from services.football_api import APIFootballError


def _stats(team_id: int, form: str = "WWDLW") -> dict:
    return {
        "team": {"id": team_id},
        "form": form,
        "goals": {
            "for": {"average": {"home": "2.0", "away": "1.5"}},
            "against": {"average": {"home": "1.0", "away": "1.2"}},
        },
        "fixtures": {"played": {"home": 10, "away": 10}, "wins": {"home": 6, "away": 4}},
    }


class TestPredictMatch:
    @pytest.mark.asyncio
    async def test_healthy_fetch_is_not_low_quality(self, monkeypatch):
        async def ok_stats(team_id, league_id, season=None):
            return _stats(team_id)

        async def ok_h2h(a, b, last=10):
            return []

        monkeypatch.setattr(prediction, "get_team_stats", ok_stats)
        monkeypatch.setattr(prediction, "get_head_to_head", ok_h2h)

        result = await prediction.predict_match(1, 2, "PL", 2025)
        assert result["is_low_quality"] is False
        assert result["home_form"] == "WWDLW"
        assert abs(sum([result["home_prob"], result["draw_prob"], result["away_prob"]]) - 100) < 0.2

    @pytest.mark.asyncio
    async def test_one_failed_source_is_flagged_low_quality_not_dropped(self, monkeypatch):
        async def failing_stats(team_id, league_id, season=None):
            raise APIFootballError(429, "rate limited")

        async def ok_h2h(a, b, last=10):
            return []

        monkeypatch.setattr(prediction, "get_team_stats", failing_stats)
        monkeypatch.setattr(prediction, "get_head_to_head", ok_h2h)

        # Should NOT raise — a prediction is still returned, just flagged.
        result = await prediction.predict_match(1, 2, "PL", 2025)
        assert result["is_low_quality"] is True
        assert result["home_form"] == ""  # no stats fetched, no form string to report

    @pytest.mark.asyncio
    async def test_failed_h2h_alone_still_flags_low_quality(self, monkeypatch):
        async def ok_stats(team_id, league_id, season=None):
            return _stats(team_id)

        async def failing_h2h(a, b, last=10):
            raise APIFootballError(500, "upstream error")

        monkeypatch.setattr(prediction, "get_team_stats", ok_stats)
        monkeypatch.setattr(prediction, "get_head_to_head", failing_h2h)

        result = await prediction.predict_match(1, 2, "PL", 2025)
        assert result["is_low_quality"] is True


class TestRuleBasedPredict:
    """The fallback's outputs are deliberately bucketed into 3 fixed triples —
    this is what caused two different matches to show byte-identical
    probabilities in production. Pinning the bucket boundaries here means any
    future change to this behavior is a deliberate, visible diff."""

    def test_strong_home_form_bucket(self):
        probs = prediction._rule_based_predict({"form_diff": 1.0, "goals_diff": 1.0})
        assert probs[0] > probs[1] > probs[2]
        assert round(probs[0] * 100, 1) == 57.1

    def test_strong_away_form_bucket(self):
        probs = prediction._rule_based_predict({"form_diff": -1.0, "goals_diff": -1.0})
        # Away is clearly favored; note the home bias (_HOME_BIAS, always
        # added to probs[0]) means home still edges out draw for 2nd place.
        assert probs[2] > probs[0]
        assert probs[2] > probs[1]
        assert round(probs[2] * 100, 1) == 52.4

    def test_balanced_form_bucket(self):
        probs = prediction._rule_based_predict({"form_diff": 0.0, "goals_diff": 0.0})
        assert abs(sum(probs) - 1.0) < 1e-9

    def test_two_different_inputs_in_the_same_bucket_are_identical(self):
        # This is exactly the production symptom: any two matches whose
        # combined score lands over the +0.20 threshold get the same output,
        # regardless of how different the underlying numbers are.
        a = prediction._rule_based_predict({"form_diff": 0.9, "goals_diff": 0.9})
        b = prediction._rule_based_predict({"form_diff": 0.21, "goals_diff": 0.21})
        assert a == b
