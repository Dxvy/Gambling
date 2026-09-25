"""
Match outcome prediction service.

Loads the trained XGBoost model at import time (once per process).
Falls back to a form-based rule model when no .pkl file is available —
useful during development before the ML model has been trained.

Prediction labels:
  HOME = 0  (home team wins)
  DRAW = 1
  AWAY = 2  (away team wins)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

import joblib
import numpy as np
from dotenv import load_dotenv

from ml.features import FEATURE_COLS, build_match_features, features_to_array
from services.football_api import get_head_to_head, get_team_stats

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading — happens once when the module is first imported
# ---------------------------------------------------------------------------

MODEL_PATH = os.getenv("MODEL_PATH", "./ml/models/xgb_model.pkl")

_model = None  # None → rule-based fallback is used

if os.path.exists(MODEL_PATH):
    try:
        _model = joblib.load(MODEL_PATH)
        logger.info("STARTUP: XGBoost model loaded from %s — predictions will use model_used=xgboost", MODEL_PATH)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "STARTUP: found a file at %s but failed to load it (%s) — "
            "falling back to model_used=rule_based", MODEL_PATH, exc,
        )
else:
    logger.warning(
        "STARTUP: no model file at %s — falling back to model_used=rule_based. "
        "Train one with ml/train.py and make sure it's deployed (not gitignored) "
        "at this path.", MODEL_PATH,
    )


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

# Thresholds that determine which outcome the rule model predicts.
# These constants were chosen to match historical home-win rates in top leagues
# (~47 % home, ~26 % draw, ~27 % away).
_FORM_DIFF_THRESHOLD = 0.20   # form difference needed to predict a decisive result
_HOME_BIAS = 0.05             # small bump added to all home probabilities


def _rule_based_predict(features: dict[str, float]) -> list[float]:
    """
    Return [home_prob, draw_prob, away_prob] using simple form + goals logic.

    This is intentionally conservative — it reflects baseline match uncertainty
    and is only used until a trained model replaces it.
    """
    form_diff  = features.get("form_diff", 0.0)
    goals_diff = features.get("goals_diff", 0.0)
    combined   = form_diff * 0.6 + goals_diff * 0.4  # weighted signal

    if combined > _FORM_DIFF_THRESHOLD:
        probs = [0.55, 0.24, 0.21]
    elif combined < -_FORM_DIFF_THRESHOLD:
        probs = [0.21, 0.24, 0.55]
    else:
        probs = [0.37, 0.28, 0.35]  # near-balanced with slight home edge

    # Ensure probabilities sum exactly to 1.0 after home bias
    probs[0] += _HOME_BIAS
    total = sum(probs)
    return [p / total for p in probs]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

OUTCOME_LABELS: list[Literal["HOME", "DRAW", "AWAY"]] = ["HOME", "DRAW", "AWAY"]


async def predict_match(
    home_id: int,
    away_id: int,
    league_id: int,
    season: int = 2024,
) -> dict:
    """
    Fetch team data concurrently, build features, and return a prediction.

    The three API calls (home stats, away stats, H2H) are issued in parallel
    with ``asyncio.gather`` to minimise latency.

    Returns
    -------
    dict with keys:
        home_prob, draw_prob, away_prob  – probabilities (0–100, one decimal)
        prediction                       – "HOME" | "DRAW" | "AWAY"
        confidence                       – highest probability as an integer %
        is_value_bet                     – always False here (set by router after
                                           comparing with bookmaker odds)
        features                         – raw feature dict for transparency
        model_used                       – "xgboost" | "rule_based"
        is_low_quality                   – True if one or more data sources failed
                                           and neutral defaults had to fill the gap
        home_form / away_form            – raw form strings (e.g. "WWDLW") for display
    """
    # Fetch all three data sources concurrently. return_exceptions=True so a
    # single failed call (e.g. rate limit exhausted) doesn't take down the
    # other two — we still want a prediction, just flagged as low quality
    # instead of silently defaulting the missing side to neutral features.
    home_stats, away_stats, h2h = await asyncio.gather(
        get_team_stats(home_id, league_id, season),
        get_team_stats(away_id, league_id, season),
        get_head_to_head(home_id, away_id, last=10),
        return_exceptions=True,
    )

    is_low_quality = False
    if isinstance(home_stats, Exception):
        logger.warning("predict_match: home team %d stats fetch failed: %s", home_id, home_stats)
        home_stats, is_low_quality = {}, True
    if isinstance(away_stats, Exception):
        logger.warning("predict_match: away team %d stats fetch failed: %s", away_id, away_stats)
        away_stats, is_low_quality = {}, True
    if isinstance(h2h, Exception):
        logger.warning("predict_match: H2H fetch failed for %d vs %d: %s", home_id, away_id, h2h)
        h2h, is_low_quality = [], True

    features = build_match_features(home_stats, away_stats, h2h)

    if _model is not None:
        # Use the trained ML model
        feat_array = features_to_array(features)
        probs = _model.predict_proba(feat_array)[0].tolist()
        model_used = "xgboost"
    else:
        # Fall back to rule-based logic while model is being trained
        probs = _rule_based_predict(features)
        model_used = "rule_based"

    predicted_idx = int(np.argmax(probs))
    prediction    = OUTCOME_LABELS[predicted_idx]
    confidence    = round(max(probs) * 100)

    return {
        "home_prob":  round(probs[0] * 100, 1),
        "draw_prob":  round(probs[1] * 100, 1),
        "away_prob":  round(probs[2] * 100, 1),
        "prediction": prediction,
        "confidence": confidence,
        "is_value_bet": False,  # enriched by the router when odds are available
        "features":   features,
        "model_used": model_used,
        "is_low_quality": is_low_quality,
        "home_form": home_stats.get("form", "") if isinstance(home_stats, dict) else "",
        "away_form": away_stats.get("form", "") if isinstance(away_stats, dict) else "",
    }


def reload_model() -> bool:
    """
    Hot-reload the model file without restarting the server.

    Call this after ``ml/train.py`` finishes training a new model.
    Returns True if the model was loaded successfully, False otherwise.
    """
    global _model  # noqa: PLW0603
    if not os.path.exists(MODEL_PATH):
        logger.warning("reload_model: no file at %s", MODEL_PATH)
        return False
    try:
        _model = joblib.load(MODEL_PATH)
        logger.info("Model reloaded from %s", MODEL_PATH)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("reload_model failed: %s", exc)
        return False


def get_model_status() -> dict:
    """Report which prediction path is currently active — used by GET /api/sports/health."""
    return {
        "model_used": "xgboost" if _model is not None else "rule_based",
        "model_path": MODEL_PATH,
        "model_file_exists": os.path.exists(MODEL_PATH),
    }
