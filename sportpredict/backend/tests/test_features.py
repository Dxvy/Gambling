"""Tests for ml/features.py — feature engineering used identically at
training time (ml/train.py) and inference time (services/prediction.py)."""

from __future__ import annotations

import numpy as np

from ml.features import (
    FEATURE_COLS,
    build_match_features,
    extract_goals_stats,
    extract_h2h_features,
    extract_win_rates,
    features_to_array,
    form_to_points,
)


class TestFormToPoints:
    def test_all_wins_is_1(self):
        assert form_to_points("WWWWW") == 1.0

    def test_all_losses_is_0(self):
        assert form_to_points("LLLLL") == 0.0

    def test_mixed_form(self):
        # W=3 D=1 L=0 -> (3+1+0+3+1)/15 = 8/15
        assert form_to_points("WDLWD") == 8 / 15

    def test_empty_string_defaults_neutral(self):
        assert form_to_points("") == 0.5

    def test_uses_only_last_n_chars(self):
        # last 5 of "WWWWWLLLLL" is "LLLLL"
        assert form_to_points("WWWWWLLLLL", last_n=5) == 0.0


class TestExtractGoalsStats:
    def test_reads_nested_averages(self):
        stats = {"goals": {"for": {"average": {"home": "2.50", "away": "1.10"}},
                            "against": {"average": {"home": "0.80", "away": "1.90"}}}}
        result = extract_goals_stats(stats)
        assert result["goals_for_home"] == 2.5
        assert result["goals_for_away"] == 1.1
        assert result["goals_against_home"] == 0.8
        assert result["goals_against_away"] == 1.9

    def test_missing_structure_defaults_to_zero(self):
        assert extract_goals_stats({}) == {
            "goals_for_home": 0.0, "goals_for_away": 0.0,
            "goals_against_home": 0.0, "goals_against_away": 0.0,
        }


class TestExtractWinRates:
    def test_computes_rate_from_played_and_wins(self):
        stats = {"fixtures": {"played": {"home": 10, "away": 8}, "wins": {"home": 6, "away": 3}}}
        result = extract_win_rates(stats)
        assert result["home_win_rate"] == 0.6
        assert result["away_win_rate"] == 0.375

    def test_no_games_played_defaults_to_league_average(self):
        stats = {"fixtures": {"played": {"home": 0, "away": 0}, "wins": {"home": 0, "away": 0}}}
        result = extract_win_rates(stats)
        assert result["home_win_rate"] == 0.33
        assert result["away_win_rate"] == 0.33


class TestExtractH2HFeatures:
    def test_empty_history_defaults_neutral(self):
        result = extract_h2h_features([], home_team_id=1)
        assert result == {"h2h_home_wins": 0.5, "h2h_goals_avg": 2.5}

    def test_counts_wins_for_correct_team_regardless_of_past_venue(self):
        # Team 1 is "home" in match A (won) and "away" in match B (so not a home win for team 1)
        h2h = [
            {"teams": {"home": {"id": 1, "winner": True}, "away": {"id": 2, "winner": False}},
             "goals": {"home": 2, "away": 0}},
            {"teams": {"home": {"id": 2, "winner": True}, "away": {"id": 1, "winner": False}},
             "goals": {"home": 1, "away": 0}},
        ]
        result = extract_h2h_features(h2h, home_team_id=1)
        assert result["h2h_home_wins"] == 0.5  # only 1 of 2 matches was a "team 1 as home, and won"
        assert result["h2h_goals_avg"] == 1.5  # (2+0 + 1+0) / 2


class TestBuildMatchFeatures:
    def _make_stats(self, team_id: int, form: str = "WWDLW") -> dict:
        return {
            "team": {"id": team_id},
            "form": form,
            "goals": {
                "for": {"average": {"home": "2.0", "away": "1.5"}},
                "against": {"average": {"home": "1.0", "away": "1.2"}},
            },
            "fixtures": {
                "played": {"home": 10, "away": 10},
                "wins": {"home": 6, "away": 4},
            },
        }

    def test_returns_exactly_feature_cols(self):
        home_stats = self._make_stats(1)
        away_stats = self._make_stats(2)
        features = build_match_features(home_stats, away_stats, [])
        assert set(features.keys()) == set(FEATURE_COLS)

    def test_diff_features_are_signed_differences(self):
        home_stats = self._make_stats(1, form="WWWWW")  # form=1.0
        away_stats = self._make_stats(2, form="LLLLL")  # form=0.0
        features = build_match_features(home_stats, away_stats, [])
        assert features["form_diff"] == 1.0
        assert features["goals_diff"] == features["home_goals_avg"] - features["away_goals_avg"]
        assert features["conceded_diff"] == features["away_conceded_avg"] - features["home_conceded_avg"]


class TestFeaturesToArray:
    def test_preserves_feature_cols_order(self):
        features = {col: float(i) for i, col in enumerate(FEATURE_COLS)}
        arr = features_to_array(features)
        assert arr.shape == (1, len(FEATURE_COLS))
        assert np.array_equal(arr[0], np.arange(len(FEATURE_COLS), dtype=np.float32))
