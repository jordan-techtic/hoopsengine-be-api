"""Authenticated player Home Screen endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.player_home import PlayerHomeResponse
from app.services import player_home as player_home_service

router = APIRouter(prefix="/player", tags=["player-home"])

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
    "/home",
    response_model=PlayerHomeResponse,
    operation_id="getPlayerHome",
    summary="Get authenticated player home screen data",
    description=(
        "Return personalized home screen data for the authenticated player.\n\n"
        "Includes user details (`user_name`, `team_name`, `jersey_number`), performance "
        "metrics (`total_sessions`, `total_attempts`), recent sessions, and a motivational "
        "quote (`motivational_card`).\n\n"
        "Optional query parameters `phone` and `company` are client metadata echoed in "
        "the response and not persisted.\n\n"
        "**Requires authenticated player JWT.**"
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
async def get_player_home(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    company: str | None = Query(
        default=None,
        description="Optional organization label from Col_Organization (not persisted)",
        examples=["Acme Realty"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerHomeResponse:
    _validate_optional_phone(phone)
    result = await player_home_service.get_player_home(
        db,
        current_user,
        phone=phone,
        company=company,
    )
    return PlayerHomeResponse(**result)
