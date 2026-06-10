"""
Feature engineering for match outcome prediction.

All functions consume the raw JSON structures returned by API-Football.
``FEATURE_COLS`` defines the canonical column order — it must be identical
during training (ml/train.py) and inference (services/prediction.py) because
scikit-learn and XGBoost address features by position, not by name.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical feature column order — never reorder without retraining the model
# ---------------------------------------------------------------------------
FEATURE_COLS: list[str] = [
    "home_form",         # recent points ratio for the home team  (0-1)
    "away_form",         # recent points ratio for the away team  (0-1)
    "home_goals_avg",    # home team's avg goals scored at home this season
    "away_goals_avg",    # away team's avg goals scored away this season
    "home_conceded_avg", # home team's avg goals conceded at home this season
    "away_conceded_avg", # away team's avg goals conceded away this season
    "home_win_rate",     # home team's home-game win rate  (0-1)
    "away_win_rate",     # away team's away-game win rate  (0-1)
    "h2h_home_wins",     # proportion of H2H matches won by the home team
    "h2h_goals_avg",     # average total goals per H2H match
    "form_diff",         # home_form  - away_form  (signed)
    "goals_diff",        # home_goals_avg - away_goals_avg  (signed)
    "conceded_diff",     # away_conceded_avg - home_conceded_avg  (positive = home advantage)
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def form_to_points(form_string: str, last_n: int = 5) -> float:
    """
    Convert a form string (e.g. ``"WWDLW"``) to a normalised points ratio.

    W=3 pts, D=1 pt, L=0 pts.  Divides by the maximum possible (3 × last_n)
    so the result is always in [0, 1].  Uses only the most recent ``last_n``
    characters to avoid stale data from early in the season.
    """
    if not form_string:
        return 0.5  # neutral fallback when data is unavailable

    mapping = {"W": 3, "D": 1, "L": 0}
    recent = form_string[-last_n:]
    earned = sum(mapping.get(c, 0) for c in recent)
    max_pts = 3 * len(recent)
    return earned / max_pts if max_pts > 0 else 0.5


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Cast to float, returning ``default`` on None, empty string, or errors."""
    try:
        return float(value) if value not in (None, "", "null") else default
    except (TypeError, ValueError):
        return default


def _extract_avg(stats: dict, key_path: list[str]) -> float:
    """
    Walk a nested dict using ``key_path`` and return the value as a float.

    Exists because the API-Football goals structure is deeply nested:
    stats["goals"]["for"]["average"]["home"] → "2.50"
    """
    node: Any = stats
    for key in key_path:
        if not isinstance(node, dict):
            return 0.0
        node = node.get(key)
    return _safe_float(node)


def _extract_count(stats: dict, key_path: list[str]) -> int:
    """Same as _extract_avg but returns an int."""
    node: Any = stats
    for key in key_path:
        if not isinstance(node, dict):
            return 0
        node = node.get(key)
    return int(_safe_float(node))


# ---------------------------------------------------------------------------
# Per-team feature extractors
# ---------------------------------------------------------------------------

def extract_goals_stats(team_stats: dict) -> dict[str, float]:
    """
    Pull goal-scoring and goal-conceding averages from the API-Football
    team/statistics response, split by home and away venues.

    Returns dict with keys: ``goals_for_home``, ``goals_for_away``,
    ``goals_against_home``, ``goals_against_away``.
    """
    return {
        "goals_for_home":     _extract_avg(team_stats, ["goals", "for",     "average", "home"]),
        "goals_for_away":     _extract_avg(team_stats, ["goals", "for",     "average", "away"]),
        "goals_against_home": _extract_avg(team_stats, ["goals", "against", "average", "home"]),
        "goals_against_away": _extract_avg(team_stats, ["goals", "against", "average", "away"]),
    }


def extract_win_rates(team_stats: dict) -> dict[str, float]:
    """
    Compute home and away win rates from fixture counts.

    Divides wins by games played for the respective venue; returns 0.33
    (league average) if no games have been played yet.
    """
    played_home  = _extract_count(team_stats, ["fixtures", "played", "home"])
    played_away  = _extract_count(team_stats, ["fixtures", "played", "away"])
    wins_home    = _extract_count(team_stats, ["fixtures", "wins",   "home"])
    wins_away    = _extract_count(team_stats, ["fixtures", "wins",   "away"])

    return {
        "home_win_rate": wins_home / played_home if played_home > 0 else 0.33,
        "away_win_rate": wins_away / played_away if played_away > 0 else 0.33,
    }


# ---------------------------------------------------------------------------
# H2H feature extractor
# ---------------------------------------------------------------------------

def extract_h2h_features(h2h: list[dict], home_team_id: int) -> dict[str, float]:
    """
    Compute historical head-to-head statistics between two teams.

    ``home_team_id`` is used to determine which team is "home" in each past
    fixture so that home wins are counted correctly.

    Returns ``h2h_home_wins`` (proportion) and ``h2h_goals_avg`` (mean total
    goals per match).
    """
    if not h2h:
        return {"h2h_home_wins": 0.5, "h2h_goals_avg": 2.5}

    home_wins = 0
    total_goals = 0

    for match in h2h:
        teams = match.get("teams", {})
        goals = match.get("goals", {})

        # Check if the "home team" in this past fixture is our current home team
        if teams.get("home", {}).get("id") == home_team_id:
            if teams.get("home", {}).get("winner"):
                home_wins += 1
        elif teams.get("away", {}).get("id") == home_team_id:
            # Our home team played away in this historical match — count as loss
            pass  # home_wins unchanged

        # Sum total goals (handles None gracefully)
        g_home = _safe_float(goals.get("home"), 0.0)
        g_away = _safe_float(goals.get("away"), 0.0)
        total_goals += g_home + g_away

    n = len(h2h)
    return {
        "h2h_home_wins": home_wins / n,
        "h2h_goals_avg": total_goals / n,
    }


# ---------------------------------------------------------------------------
# Main feature builder
# ---------------------------------------------------------------------------

def build_match_features(
    home_stats: dict,
    away_stats: dict,
    h2h: list[dict],
) -> dict[str, float]:
    """
    Build a complete feature vector for a single match.

    Parameters
    ----------
    home_stats : dict
        API-Football /teams/statistics response for the home team.
    away_stats : dict
        API-Football /teams/statistics response for the away team.
    h2h : list[dict]
        API-Football /fixtures/headtohead response (list of past matches).

    Returns
    -------
    dict
        Keys match ``FEATURE_COLS`` exactly.  Missing API values fall back to
        neutral defaults so prediction never raises a KeyError.
    """
    home_form = form_to_points(home_stats.get("form", ""))
    away_form = form_to_points(away_stats.get("form", ""))

    home_goals = extract_goals_stats(home_stats)
    away_goals = extract_goals_stats(away_stats)
    home_rates = extract_win_rates(home_stats)
    away_rates = extract_win_rates(away_stats)

    home_team_id = home_stats.get("team", {}).get("id")
    h2h_feats = extract_h2h_features(h2h, home_team_id)

    home_goals_avg    = home_goals["goals_for_home"]
    away_goals_avg    = away_goals["goals_for_away"]
    home_conceded_avg = home_goals["goals_against_home"]
    away_conceded_avg = away_goals["goals_against_away"]

    return {
        "home_form":         home_form,
        "away_form":         away_form,
        "home_goals_avg":    home_goals_avg,
        "away_goals_avg":    away_goals_avg,
        "home_conceded_avg": home_conceded_avg,
        "away_conceded_avg": away_conceded_avg,
        "home_win_rate":     home_rates["home_win_rate"],
        "away_win_rate":     away_rates["away_win_rate"],
        "h2h_home_wins":     h2h_feats["h2h_home_wins"],
        "h2h_goals_avg":     h2h_feats["h2h_goals_avg"],
        "form_diff":         home_form - away_form,
        "goals_diff":        home_goals_avg - away_goals_avg,
        # Positive = home team concedes less than away team does away → home advantage
        "conceded_diff":     away_conceded_avg - home_conceded_avg,
    }


def features_to_array(features: dict[str, float]) -> np.ndarray:
    """
    Convert a features dict to a 1×N numpy array in ``FEATURE_COLS`` order.

    This is what gets passed to ``model.predict_proba()``.
    Raises ``KeyError`` if a required feature is missing — callers should
    ensure ``build_match_features`` was used to produce the dict.
    """
    ordered = [features[col] for col in FEATURE_COLS]
    return np.array(ordered, dtype=np.float32).reshape(1, -1)


def features_to_dataframe(feature_rows: list[dict[str, float]]) -> pd.DataFrame:
    """
    Convert a list of feature dicts into a DataFrame with canonical column order.

    Used by ``ml/train.py`` to prepare the training matrix.
    """
    return pd.DataFrame(feature_rows, columns=FEATURE_COLS)
