"""
Lottery number generation router.

Supported lottery types:
  loto         — FDJ Loto: 5 from 1-49 + 1 complémentaire (1-10)
  euromillions — EuroMillions: 5 from 1-50 + 2 stars (1-12)
  keno         — FDJ Keno: 20 from 1-70
  pmu          — PMU Quinté+: 5 picks from 1-18

Hot/cold statistics are derived from pre-generated mock history (fixed seed so
the hot/cold numbers are consistent across server restarts).  Replace
``_MOCK_HISTORY`` with real draw data when available via FDJ open data or a
scraper.

Endpoints:
  GET  /api/lottery/config/{lottery}   → LotteryConfigResponse
  GET  /api/lottery/hot-cold/{lottery} → HotColdResponse
  GET  /api/lottery/suggest/{lottery}  → SuggestionResponse
  POST /api/lottery/insight            → AI commentary for a generated grid
"""

from __future__ import annotations

import logging
import random as _stdlib_random
from collections import Counter
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.ai_insight import AIInsightError, InsightResponse, generate_lottery_insight

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Lottery configurations
# ---------------------------------------------------------------------------

# All lottery parameters live here — no magic numbers scattered in logic below
LOTTERY_CONFIGS: dict[str, dict] = {
    "loto": {
        "label":       "Loto FDJ",
        "max":         49,      # highest main number
        "count":       5,       # how many main numbers to pick
        "bonus_max":   10,      # highest bonus number
        "bonus_count": 1,       # how many bonus numbers
    },
    "euromillions": {
        "label":       "EuroMillions",
        "max":         50,
        "count":       5,
        "bonus_max":   12,      # EuroMillions stars: 1-12
        "bonus_count": 2,       # two star numbers
    },
    "keno": {
        "label":       "Keno FDJ",
        "max":         70,
        "count":       20,      # keno picks 20 numbers
        "bonus_max":   None,
        "bonus_count": 0,
    },
    "pmu": {
        "label":       "Quinté+ PMU",
        "max":         18,      # typical Quinté+ field size
        "count":       5,
        "bonus_max":   None,
        "bonus_count": 0,
    },
}

_VALID_LOTTERY_NAMES = frozenset(LOTTERY_CONFIGS)
_VALID_STRATEGIES    = frozenset({"hot", "cold", "balanced", "random"})


def _require_lottery(name: str) -> dict:
    """Raise 404 with a helpful message if the lottery name is unknown."""
    if name not in _VALID_LOTTERY_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown lottery '{name}'. Valid values: {sorted(_VALID_LOTTERY_NAMES)}",
        )
    return LOTTERY_CONFIGS[name]


# ---------------------------------------------------------------------------
# Mock history generation (fixed seed = deterministic hot/cold patterns)
# ---------------------------------------------------------------------------

# Use a fixed seed so the same numbers are always "hot" — a consistent demo
_HISTORY_RNG = _stdlib_random.Random(1337)


def _generate_mock_history(config: dict, n_draws: int = 60) -> list[list[int]]:
    """
    Generate synthetic draw history with realistic hot/cold distribution.

    A fraction of numbers are given higher weights (hot) or lower weights (cold)
    so the statistics page shows interesting patterns without real data.
    """
    max_n = config["max"]
    count = config["count"]
    pool  = list(range(1, max_n + 1))

    # Decide which numbers will be hot / cold (seeded so it's reproducible)
    n_extreme   = max(5, len(pool) // 8)
    hot_indices = set(_HISTORY_RNG.sample(range(len(pool)), n_extreme))
    cold_indices = set(
        _HISTORY_RNG.sample(
            [i for i in range(len(pool)) if i not in hot_indices],
            n_extreme,
        )
    )

    weights = [1.0] * len(pool)
    for i in hot_indices:  weights[i] = 3.0
    for i in cold_indices: weights[i] = 0.15

    history: list[list[int]] = []
    for _ in range(n_draws):
        # Weighted sample without replacement
        remaining = list(zip(pool, weights))
        draw: list[int] = []
        for _ in range(count):
            total = sum(w for _, w in remaining)
            r     = _HISTORY_RNG.random() * total
            cum   = 0.0
            for j, (num, w) in enumerate(remaining):
                cum += w
                if r <= cum:
                    draw.append(num)
                    remaining.pop(j)
                    break
        history.append(sorted(draw))

    return history


# Build history once at module load — fast (< 10 ms total)
_MOCK_HISTORY: dict[str, list[list[int]]] = {
    name: _generate_mock_history(cfg)
    for name, cfg in LOTTERY_CONFIGS.items()
}


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class LotteryConfigResponse(BaseModel):
    name:        str
    label:       str
    max:         int
    count:       int
    bonus_max:   int | None
    bonus_count: int


class HotColdResponse(BaseModel):
    lottery:        str
    hot:            list[int] = Field(description="Top 10 most frequent main numbers")
    cold:           list[int] = Field(description="Bottom 10 least frequent main numbers")
    frequency:      dict[str, int] = Field(description="Appearance count per number key")
    draws_analyzed: int


class SuggestionResponse(BaseModel):
    lottery:  str
    numbers:  list[int] = Field(description="Suggested main numbers, sorted ascending")
    bonus:    list[int] = Field(description="Suggested bonus numbers (0, 1, or 2 items)")
    strategy: str


class LotteryInsightRequest(BaseModel):
    lottery:  str
    numbers:  list[int]
    bonus:    list[int] = []
    strategy: str


# ---------------------------------------------------------------------------
# Internal suggestion helpers
# ---------------------------------------------------------------------------

def _pad_to_count(
    pool:       list[int],
    count:      int,
    all_numbers: set[int],
) -> list[int]:
    """
    Return exactly ``count`` numbers from ``pool``, padding with random extras
    from ``all_numbers`` if the pool is too small.

    This is important for the keno hot/cold strategy: there are only 10 hot
    numbers but we need to pick 20 — so the remaining 10 come from the rest.
    """
    if len(pool) >= count:
        return _stdlib_random.sample(pool, count)
    extras = list(all_numbers - set(pool))
    needed = count - len(pool)
    return pool + _stdlib_random.sample(extras, min(needed, len(extras)))


def _build_suggestion(
    config:   dict,
    hot:      list[int],
    cold:     list[int],
    strategy: str,
) -> list[int]:
    """
    Build a list of ``count`` main numbers according to the requested strategy.

    Strategies:
      hot      — drawn from the most frequent numbers (padded if needed)
      cold     — drawn from the least frequent numbers (padded if needed)
      random   — uniformly random from the full range
      balanced — roughly ⅓ hot, ¼ cold, rest neutral
    """
    count    = config["count"]
    all_nums = set(range(1, config["max"] + 1))

    if strategy == "hot":
        pool = hot[: count * 2]  # take a generous slice so sampling works
        return sorted(_pad_to_count(pool, count, all_nums))

    if strategy == "cold":
        pool = cold[: count * 2]
        return sorted(_pad_to_count(pool, count, all_nums))

    if strategy == "random":
        return sorted(_stdlib_random.sample(list(all_nums), count))

    # balanced: ~⅓ from hot, ~¼ from cold, remainder from neutral
    n_hot  = max(1, count // 3)
    n_cold = max(1, count // 4)
    n_mid  = count - n_hot - n_cold

    hot_pick  = _stdlib_random.sample(hot[:n_hot  * 3], min(n_hot,  len(hot)))
    cold_pick = _stdlib_random.sample(cold[:n_cold * 3], min(n_cold, len(cold)))
    used      = set(hot_pick) | set(cold_pick)
    neutral   = list(all_nums - used)
    mid_pick  = _stdlib_random.sample(neutral, min(n_mid, len(neutral)))

    result = hot_pick + cold_pick + mid_pick
    # If still short, top up with random neutrals
    if len(result) < count:
        extra = list(all_nums - set(result))
        result += _stdlib_random.sample(extra, count - len(result))

    return sorted(result[:count])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/config/{lottery}",
    response_model=LotteryConfigResponse,
    summary="Return configuration for a lottery type",
)
def get_config(lottery: str) -> LotteryConfigResponse:
    """Return the parameters (max number, pick count, bonus info) for one lottery."""
    cfg = _require_lottery(lottery)
    return LotteryConfigResponse(name=lottery, **cfg)


def _hot_cold_impl(lottery: str, last_draws: int = 50, top_n: int = 10) -> HotColdResponse:
    """
    Pure-function core for hot/cold stats — callable both by the endpoint and
    by ``suggest_numbers`` internally without hitting FastAPI's Query machinery.
    """
    cfg = _require_lottery(lottery)

    draws    = _MOCK_HISTORY[lottery][:last_draws]
    all_nums = [n for draw in draws for n in draw]
    counter  = Counter(all_nums)

    # Every number in 1..max must appear (frequency 0 if never drawn)
    full_freq      = {n: counter.get(n, 0) for n in range(1, cfg["max"] + 1)}
    sorted_by_freq = sorted(full_freq.items(), key=lambda x: x[1])

    # Cap top_n so hot and cold lists never overlap (requires 2*n < max)
    effective_top_n = min(top_n, (cfg["max"] - 1) // 2)

    cold = [n for n, _ in sorted_by_freq[:effective_top_n]]
    hot  = [n for n, _ in sorted_by_freq[-effective_top_n:]][::-1]   # highest frequency first

    return HotColdResponse(
        lottery        = lottery,
        hot            = hot,
        cold           = cold,
        # String keys: JSON object keys are strings; frontend reads frequencyMap[String(n)]
        frequency      = {str(k): v for k, v in full_freq.items()},
        draws_analyzed = len(draws),
    )


@router.get(
    "/hot-cold/{lottery}",
    response_model=HotColdResponse,
    summary="Return hot and cold number statistics",
)
def get_hot_cold(
    lottery:    str,
    last_draws: int = Query(50, ge=5, le=200, description="Number of past draws to analyse"),
    top_n:      int = Query(10, ge=3, le=20,  description="How many numbers in hot/cold lists"),
) -> HotColdResponse:
    """
    Count number frequencies across the last N draws and classify them as
    hot (most frequent) or cold (least frequent).

    Frequencies are returned as a dict so the frontend can use them to render
    a heat gradient on the number grid.
    """
    return _hot_cold_impl(lottery, last_draws, top_n)


@router.get(
    "/suggest/{lottery}",
    response_model=SuggestionResponse,
    summary="Generate a number suggestion for a lottery",
)
def suggest_numbers(
    lottery:  str,
    strategy: str = Query(
        "balanced",
        description="Suggestion strategy: hot | cold | balanced | random",
    ),
) -> SuggestionResponse:
    """
    Generate a complete set of numbers (main + bonus) for the requested lottery
    using the chosen strategy.

    The strategy only applies to main numbers.  Bonus numbers (lucky number,
    stars) are always drawn uniformly at random from their valid range.
    """
    cfg = _require_lottery(lottery)

    if strategy not in _VALID_STRATEGIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy '{strategy}'. Valid: {sorted(_VALID_STRATEGIES)}",
        )

    # Build hot/cold lists from default draw window (use impl directly — not the FastAPI endpoint)
    hc      = _hot_cold_impl(lottery)
    numbers = _build_suggestion(cfg, hc.hot, hc.cold, strategy)

    # Draw bonus numbers (stars, complémentaire) uniformly at random
    bonus: list[int] = []
    if cfg["bonus_max"] and cfg["bonus_count"] > 0:
        bonus = sorted(
            _stdlib_random.sample(
                range(1, cfg["bonus_max"] + 1),
                cfg["bonus_count"],
            )
        )

    return SuggestionResponse(lottery=lottery, numbers=numbers, bonus=bonus, strategy=strategy)


@router.post(
    "/insight",
    response_model=InsightResponse,
    summary="Generate AI commentary for a lottery grid",
)
async def lottery_insight(payload: LotteryInsightRequest) -> InsightResponse:
    """Ask Claude for a short, lighthearted comment about a generated grid."""
    try:
        text = await generate_lottery_insight(**payload.model_dump())
    except AIInsightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return InsightResponse(insight=text)
