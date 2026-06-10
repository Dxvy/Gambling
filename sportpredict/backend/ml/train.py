"""
XGBoost training script for match outcome prediction.

Usage
-----
    # Train from a CSV file
    python ml/train.py --data ml/data/historical_matches.csv

    # Override model output path
    python ml/train.py --data ml/data/historical_matches.csv --out ml/models/xgb_v2.pkl

    # Use LightGBM instead of XGBoost
    python ml/train.py --data ml/data/historical_matches.csv --algo lgbm

CSV format expected
-------------------
One row per match.  Required columns (see FEATURE_COLS in ml/features.py):

    home_form, away_form, home_goals_avg, away_goals_avg,
    home_conceded_avg, away_conceded_avg, home_win_rate, away_win_rate,
    h2h_home_wins, h2h_goals_avg, form_diff, goals_diff, conceded_diff,
    result   ← integer: 0 = Home win, 1 = Draw, 2 = Away win

Where to get historical data
-----------------------------
Option A — API-Football (free tier: 100 req/day)
    curl "https://v3.football.api-sports.io/fixtures?league=39&season=2022"
    Collect 3–5 seasons to reach 3 000+ matches for a meaningful model.

Option B — Free CSV datasets
    https://www.football-data.co.uk/  (one CSV per league/season, no signup)

Option C — Kaggle
    Search "football match results dataset" — several high-quality datasets.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from ml.features import FEATURE_COLS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

def _build_xgboost(**kwargs):
    from xgboost import XGBClassifier
    defaults = dict(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=42,
    )
    return XGBClassifier(**{**defaults, **kwargs})


def _build_lightgbm(**kwargs):
    from lightgbm import LGBMClassifier
    defaults = dict(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,  # silence LightGBM's own logging
    )
    return LGBMClassifier(**{**defaults, **kwargs})


ALGO_MAP = {"xgb": _build_xgboost, "lgbm": _build_lightgbm}


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def load_and_validate(data_path: str) -> tuple[pd.DataFrame, pd.Series]:
    """
    Load the CSV and validate that all required columns are present.
    Returns (X, y) as DataFrame and Series.
    """
    logger.info("Loading data from %s", data_path)
    df = pd.read_csv(data_path)

    required = FEATURE_COLS + ["result"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("Missing columns in CSV: %s", missing)
        sys.exit(1)

    # Drop rows with NaN in any feature or target column
    before = len(df)
    df = df.dropna(subset=required)
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with NaN values", dropped)

    logger.info("Dataset: %d rows, class distribution: %s",
                len(df), df["result"].value_counts().to_dict())

    X = df[FEATURE_COLS]
    y = df["result"].astype(int)
    return X, y


def evaluate(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """
    Compute accuracy and log-loss on the held-out test set.
    Returns a metrics dict for logging/saving alongside the model.
    """
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    acc     = accuracy_score(y_test, y_pred)
    ll      = log_loss(y_test, y_proba)
    logger.info("Test accuracy: %.3f  |  Log-loss: %.4f", acc, ll)
    return {"accuracy": round(acc, 4), "log_loss": round(ll, 4)}


def print_feature_importance(model, algo: str) -> None:
    """Log the top-5 features by importance — useful for debugging bad predictions."""
    try:
        if algo == "xgb":
            scores = model.feature_importances_
        elif algo == "lgbm":
            scores = model.feature_importances_
        else:
            return

        pairs = sorted(zip(FEATURE_COLS, scores), key=lambda x: x[1], reverse=True)
        logger.info("Top feature importances:")
        for name, score in pairs[:5]:
            logger.info("  %-25s %.4f", name, score)
    except AttributeError:
        pass  # model type doesn't expose importances


def train(
    data_path: str,
    out_path: str = "ml/models/xgb_model.pkl",
    algo: str = "xgb",
    test_size: float = 0.15,
    cv_folds: int = 5,
) -> None:
    """
    Full training pipeline:
      1. Load + validate data
      2. Stratified train/test split
      3. Fit model
      4. Cross-validation on training set (optional sanity check)
      5. Evaluate on held-out test set
      6. Log feature importances
      7. Save model to disk

    Parameters
    ----------
    data_path  : path to the CSV file
    out_path   : where to save the trained model (.pkl)
    algo       : "xgb" (XGBoost) or "lgbm" (LightGBM)
    test_size  : fraction of data held out for final evaluation
    cv_folds   : number of folds for cross-validation on training set
    """
    X, y = load_and_validate(data_path)

    # Stratified split preserves class balance in both sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=42
    )
    logger.info("Train: %d rows  |  Test: %d rows", len(X_train), len(X_test))

    builder = ALGO_MAP.get(algo)
    if builder is None:
        logger.error("Unknown algorithm '%s'. Choose from: %s", algo, list(ALGO_MAP))
        sys.exit(1)

    model = builder()

    # Cross-validation on training set — a quick sanity check before full fit
    logger.info("Running %d-fold CV on training set…", cv_folds)
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
    logger.info("CV accuracy: %.3f ± %.3f", cv_scores.mean(), cv_scores.std())

    # Fit on the full training set
    logger.info("Fitting final model on full training set…")
    model.fit(X_train, y_train)

    metrics = evaluate(model, X_test, y_test)
    print_feature_importance(model, algo)

    # Persist model to disk
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump(model, out_path)
    logger.info("Model saved to %s  |  metrics: %s", out_path, metrics)

    logger.info(
        "\nDone!  To hot-reload without restarting the server:\n"
        "  POST http://localhost:8000/api/sports/reload-model"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the SportPredict prediction model.")
    parser.add_argument(
        "--data", required=True,
        help="Path to training CSV (see module docstring for required columns)",
    )
    parser.add_argument(
        "--out", default="ml/models/xgb_model.pkl",
        help="Output path for the saved model (default: ml/models/xgb_model.pkl)",
    )
    parser.add_argument(
        "--algo", choices=list(ALGO_MAP), default="xgb",
        help="Algorithm to use: xgb (XGBoost) or lgbm (LightGBM). Default: xgb",
    )
    parser.add_argument(
        "--test-size", type=float, default=0.15,
        help="Fraction of data held out for evaluation (default: 0.15)",
    )
    parser.add_argument(
        "--cv-folds", type=int, default=5,
        help="Number of cross-validation folds (default: 5)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train(
        data_path=args.data,
        out_path=args.out,
        algo=args.algo,
        test_size=args.test_size,
        cv_folds=args.cv_folds,
    )
