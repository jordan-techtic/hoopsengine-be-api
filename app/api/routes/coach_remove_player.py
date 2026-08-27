"""Coach Remove Player endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_removal import (
    REMOVAL_CONFIRMATION_MESSAGE,
    PlayerRemovalConfirmResponse,
    PlayerRemovalRequest,
    PlayerRemovalResponse,
)
from app.services import player_removal as player_removal_service

router = APIRouter(prefix="/coach", tags=["coach-remove-player"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "User is not an authenticated verified coach",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid removal fields",
        examples={
            "empty_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Phone number must contain 10 to 15 digits",
                "details": [
                    {"field": "phone", "message": "Phone number must contain 10 to 15 digits"}
                ],
            },
            "empty_full_name": {
                "code": "VALIDATION_ERROR",
                "message": "Full name is required",
                "details": [{"field": "full_name", "message": "Full name is required"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    409: openapi_error_examples(
        "No matching player found for the submitted credentials",
        examples={
            "player_not_found": {
                "code": "PLAYER_NOT_FOUND",
                "message": "No matching player was found for the provided details",
                "details": [
                    {
                        "field": "email",
                        "message": "No matching player was found for the provided details",
                    }
                ],
            },
            "ambiguous_match": {
                "code": "PLAYER_REMOVAL_AMBIGUOUS",
                "message": "Multiple players match the provided details",
                "details": [
                    {
                        "field": "email",
                        "message": "Multiple players match the provided details",
                    }
                ],
            },
        },
    ),
}


@router.get(
    "/confirm_removal",
    response_model=PlayerRemovalConfirmResponse,
    operation_id="getPlayerRemovalConfirmation",
    summary="Get player removal confirmation copy",
    description=(
        "Return the confirmation modal message for the **Remove Player** screen.\n\n"
        "**Requires authenticated verified coach JWT** (`Authorization: Bearer <access_token>`).\n\n"
        f"The `confirmation_message` and `description` fields contain:\n\n"
        f'"{REMOVAL_CONFIRMATION_MESSAGE}"\n\n'
        "Optional query parameters `full_name`, `email`, and `phone` let the client "
        "preview whether the Remove Player button may be enabled (`can_remove=true`) "
        "when all three fields are present and valid."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_player_removal_confirmation(
    full_name: str | None = Query(
        default=None,
        description="Optional player full name preview for button enablement",
        examples=["Jane Doe"],
    ),
    email: str | None = Query(
        default=None,
        description="Optional player email preview for button enablement",
        examples=["sarah.jenkins@school.edu"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional player phone preview for button enablement",
        examples=["(555) 123-4567"],
    ),
    current_user: User = Depends(get_current_coach),
) -> PlayerRemovalConfirmResponse:
    """Return permanent deletion confirmation copy for the Remove Player modal."""
    _ = current_user
    result = player_removal_service.get_removal_confirmation(
        full_name=full_name,
        email=email,
        phone=phone,
    )
    return PlayerRemovalConfirmResponse(**result)


@router.post(
    "/remove_player",
    response_model=PlayerRemovalResponse,
    status_code=status.HTTP_200_OK,
    operation_id="removePlayerByCredentials",
    summary="Remove player by email and phone",
    description=(
        "Remove a player from the coach roster after confirming their identity with "
        "`full_name`, `email`, and `phone`.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Returns **200** when the player is removed successfully.\n\n"
        "Returns **400** when required fields are empty or email/phone formats are invalid.\n\n"
        "Returns **409** when no active player in the coach organization matches the "
        "submitted credentials."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def remove_player(
    body: PlayerRemovalRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> PlayerRemovalResponse:
    """Remove a player using email, phone, and full name confirmation."""
    result = await player_removal_service.remove_player_by_credentials(db, current_user, body)
    return PlayerRemovalResponse(**result)
