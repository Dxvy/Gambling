"""
Web Push notification service — wraps pywebpush to send notifications to
browser push subscriptions stored in ``push_subscriptions``.
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from pywebpush import WebPushException, webpush

load_dotenv()

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")


def send_push_notification(
    subscription_info: dict,
    title: str,
    body: str,
    url: str = "/",
) -> bool:
    """
    Send a single Web Push notification.

    Returns ``False`` (and logs a warning) on failure rather than raising —
    a stale or revoked subscription should never break the calling job.
    """
    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not configured — skipping push notification")
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
        )
        return True
    except WebPushException as exc:
        logger.warning("Push notification failed: %s", exc)
        return False
