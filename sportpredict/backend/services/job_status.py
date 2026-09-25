"""
In-memory status tracking for background jobs (fixture refresh, prediction
precompute), exposed via GET /api/sports/health.

This is intentionally lightweight — no external monitoring service is wired
up, so this just gives a single URL to check instead of grepping Railway
logs to answer "is the pipeline actually working?" (see the model-fallback /
0-predictions-written incidents this was built to make visible).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_status: dict[str, Any] = {
    "fixtures_refresh": {"last_run_at": None, "fixture_count": None, "last_error": None},
    "predictions_precompute": {"last_run_at": None, "predictions_written": None, "last_error": None},
}


def record_fixtures_refresh(fixture_count: int, error: str | None = None) -> None:
    _status["fixtures_refresh"] = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "fixture_count": fixture_count,
        "last_error": error,
    }


def record_precompute(written: int, error: str | None = None) -> None:
    _status["predictions_precompute"] = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "predictions_written": written,
        "last_error": error,
    }


def get_status() -> dict[str, Any]:
    return _status
