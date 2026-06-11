"""
Resolves pending predictions in ``prediction_history`` against finished
matches, then notifies users of the outcome via Web Push.

Runs periodically via the AsyncIOScheduler set up in main.py, and can also be
triggered manually via POST /api/notifications/resolve-predictions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from services.football_api import APIFootballError, get_match_result
from services.push import send_push_notification
from services.supabase_admin import get_admin_client

logger = logging.getLogger(__name__)

# Maps the league names stored in prediction_history.league to football-data.org
# competition codes. Only the leagues available on the free tier are listed —
# others (Ligue 2, La Liga 2, 2. Bundesliga, Serie B, Europa League) are skipped.
LEAGUE_NAME_TO_FD_CODE: dict[str, str] = {
    "Premier League":   "PL",
    "Championship":     "ELC",
    "La Liga":          "PD",
    "Bundesliga":       "BL1",
    "Serie A":          "SA",
    "Ligue 1":          "FL1",
    "Champions League": "CL",
}

# football-data.org free tier allows 10 requests/minute.
_REQUEST_DELAY_SECONDS = 6


async def resolve_pending_predictions() -> int:
    """
    Find predictions whose match has already happened but have no result yet,
    look up the actual outcome, fill in result/correct, and push a notification
    to the owning user. Returns the number of predictions resolved.
    """
    client = get_admin_client()
    if client is None:
        logger.warning("Supabase admin client not configured — skipping resolution")
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    pending = (
        client.table("prediction_history")
        .select("*")
        .is_("result", "null")
        .lt("matchDate", now_iso)
        .execute()
    )

    resolved = 0

    for row in pending.data:
        code = LEAGUE_NAME_TO_FD_CODE.get(row["league"])
        if not code:
            continue

        try:
            outcome = await get_match_result(
                code, row["homeTeam"], row["awayTeam"], row["matchDate"],
            )
        except APIFootballError as exc:
            logger.warning("Result lookup failed for prediction %s: %s", row["id"], exc)
            continue

        if outcome is None:
            await asyncio.sleep(_REQUEST_DELAY_SECONDS)
            continue

        correct = outcome == row["prediction"]
        client.table("prediction_history").update(
            {"result": outcome, "correct": correct}
        ).eq("id", row["id"]).execute()
        resolved += 1

        _notify_user(client, row, outcome, correct)

        await asyncio.sleep(_REQUEST_DELAY_SECONDS)

    return resolved


def _notify_user(client, row: dict, outcome: str, correct: bool) -> None:
    """Push a result notification to every device the user subscribed from."""
    subs = (
        client.table("push_subscriptions")
        .select("*")
        .eq("user_id", row["user_id"])
        .execute()
    )

    title = "Prediction resolved"
    verdict = "You called it!" if correct else "Missed this one."
    body = f"{row['homeTeam']} vs {row['awayTeam']} — {verdict} (Result: {outcome})"

    for sub in subs.data:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        send_push_notification(subscription_info, title, body, url="/dashboard")
