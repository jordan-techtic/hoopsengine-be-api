"""Authenticated player My Progress endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.player_progress import (
    DrillPerformanceResponse,
    MyProgressResponse,
    SessionHistoryResponse,
)
from app.services import player_progress as player_progress_service

router = APIRouter(prefix="/player", tags=["player-progress"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not a player",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid optional query parameters",
        code="VALIDATION_ERROR",
        message="Phone number must contain at least one digit",
        details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
    ),
}

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "No roster profile linked to the authenticated player account",
        code="PLAYER_NOT_FOUND",
        message="Player not found",
    ),
}


def _validate_optional_phone(phone: str | None) -> None:
    """Validate optional Figma status-bar phone metadata when provided."""
    if phone is None or not phone.strip():
        return
    cleaned = phone.strip()
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is invalid",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is invalid"}],
        )
    if not re.sub(r"\D", "", cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain at least one digit",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
        )


@router.get(
    "/my-progress",
    response_model=MyProgressResponse,
    operation_id="getPlayerMyProgress",
    summary="Get authenticated player progress summary",
    description=(
        "Return aggregate progress metrics for the **My Progress** screen.\n\n"
        "Includes `completed_sessions`, `total_attempts`, `makes`, and "
        "`shooting_percentage` for the authenticated player.\n\n"
        "Optional query parameter `phone` accepts Figma status-bar metadata; "
        "invalid values return **400**.\n\n"
        "Returns **404** when no roster profile is linked to the authenticated account.\n\n"
        "**Requires authenticated player JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_my_progress(
    phone: str | None = Query(
        default=None,
        description="Optional client phone value from the status bar (display format allowed)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> MyProgressResponse:
    """Return aggregate shooting progress for the authenticated player."""
    _validate_optional_phone(phone)
    result = await player_progress_service.get_my_progress(
        db,
        current_user,
        phone=phone,
    )
    return MyProgressResponse(**result)


@router.get(
    "/session-history",
    response_model=SessionHistoryResponse,
    operation_id="getPlayerSessionHistory",
    summary="Get authenticated player session history",
    description=(
        "Return drill session history rows for the **My Progress** screen.\n\n"
        "Each row includes `date` (ISO YYYY-MM-DD), `drill`, `attempts`, and `makes`.\n\n"
        "Optional query parameter `phone` accepts Figma status-bar metadata; "
        "invalid values return **400**.\n\n"
        "Returns an empty `session_history` array with `status=empty` when no sessions "
        "have been logged.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_session_history(
    phone: str | None = Query(
        default=None,
        description="Optional client phone value from the status bar (display format allowed)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> SessionHistoryResponse:
    """Return session history for the authenticated player."""
    _validate_optional_phone(phone)
    result = await player_progress_service.get_session_history(
        db,
        current_user,
        phone=phone,
    )
    return SessionHistoryResponse(**result)


@router.get(
    "/drill-performance",
    response_model=DrillPerformanceResponse,
    operation_id="getPlayerDrillPerformance",
    summary="Get authenticated player drill performance",
    description=(
        "Return per-drill performance metrics for the **My Progress** screen.\n\n"
        "Each item includes `drill`, `attempts`, `makes`, and `shooting_percentage`.\n\n"
        "Optional query parameter `phone` accepts Figma status-bar metadata; "
        "invalid values return **400**.\n\n"
        "Returns an empty `drill_performance` array with `status=empty` when no drill "
        "data is available.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_drill_performance(
    phone: str | None = Query(
        default=None,
        description="Optional client phone value from the status bar (display format allowed)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> DrillPerformanceResponse:
    """Return drill performance metrics for the authenticated player."""
    _validate_optional_phone(phone)
    result = await player_progress_service.get_drill_performance(
        db,
        current_user,
        phone=phone,
    )
    return DrillPerformanceResponse(**result)
