"""
AI commentary service — wraps the Anthropic API to generate short, human-readable
insights for match predictions and lottery grids.
"""

from __future__ import annotations

import logging
import os

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_MODEL = "claude-haiku-4-5-20251001"

_client = AsyncAnthropic(api_key=_API_KEY) if _API_KEY else None


class AIInsightError(Exception):
    """Raised when an AI insight cannot be generated."""


class InsightResponse(BaseModel):
    insight: str


async def _complete(prompt: str, max_tokens: int) -> str:
    if _client is None:
        raise AIInsightError("ANTHROPIC_API_KEY is not configured")

    try:
        response = await _client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # anthropic.APIError and subclasses
        logger.warning("Anthropic API error: %s", exc)
        raise AIInsightError(str(exc)) from exc

    return response.content[0].text.strip()


async def generate_match_insight(
    home_team: str,
    away_team: str,
    league: str,
    home_prob: float,
    draw_prob: float,
    away_prob: float,
    prediction: str,
    confidence: int,
    home_form: str = "",
    away_form: str = "",
    is_value_bet: bool = False,
    edge: float | None = None,
) -> str:
    """Generate a short (2-3 sentence) insight for an upcoming match prediction."""
    prompt = (
        f"You are a sharp football analyst. Write a short (2-3 sentence) insight "
        f"for this upcoming {league} match:\n\n"
        f"{home_team} vs {away_team}\n"
        f"Model prediction: {prediction} ({confidence}% confidence)\n"
        f"Win probabilities — Home: {home_prob:.0f}%, Draw: {draw_prob:.0f}%, "
        f"Away: {away_prob:.0f}%\n"
    )
    if home_form or away_form:
        prompt += (
            f"Recent form (oldest to newest) — {home_team}: {home_form or 'N/A'}, "
            f"{away_team}: {away_form or 'N/A'}\n"
        )
    if is_value_bet and edge is not None:
        prompt += (
            f"This is flagged as a value bet with a {edge:.1f}% edge over the "
            f"bookmaker odds.\n"
        )
    prompt += (
        "\nExplain briefly why the model favors this outcome and what to watch "
        "for. Be concise and conversational."
    )

    return await _complete(prompt, max_tokens=200)


async def generate_lottery_insight(
    lottery: str,
    numbers: list[int],
    bonus: list[int],
    strategy: str,
) -> str:
    """Generate a short, lighthearted comment about a generated lottery grid."""
    numbers_str = ", ".join(str(n) for n in numbers)
    bonus_str = ", ".join(str(n) for n in bonus) if bonus else "none"

    prompt = (
        f"You are a witty lottery commentator. A user generated this {lottery} "
        f"grid using the '{strategy}' strategy:\n\n"
        f"Numbers: {numbers_str}\n"
        f"Bonus: {bonus_str}\n\n"
        f"Write a short (2-3 sentence), fun and lighthearted comment about this "
        f"combination. You may mention number patterns, but always remind the "
        f"reader (briefly, with humor) that lottery draws are random and this is "
        f"for entertainment only."
    )

    return await _complete(prompt, max_tokens=150)
