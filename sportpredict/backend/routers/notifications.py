"""
FastAPI router for admin/notification endpoints.

Endpoints
---------
POST /api/notifications/resolve-predictions    Manually trigger resolution of
                                                 pending predictions (admin/testing)
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from services.results_resolver import resolve_pending_predictions

router = APIRouter()


class ResolveResponse(BaseModel):
    resolved: int


@router.post(
    "/resolve-predictions",
    response_model=ResolveResponse,
    summary="Manually trigger resolution of pending predictions",
)
async def resolve_predictions_endpoint() -> ResolveResponse:
    """
    Check finished matches for any prediction still missing a result, fill in
    result/correct, and notify the owning user via push. The same job also
    runs automatically every few hours via the scheduler in main.py.
    """
    resolved = await resolve_pending_predictions()
    return ResolveResponse(resolved=resolved)
