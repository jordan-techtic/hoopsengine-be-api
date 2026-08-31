"""Authenticated player profile endpoints for the Edit Profile screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_profile import PlayerProfileResponse, PlayerProfileUpdateRequest
from app.services import player_profile as player_profile_service

router = APIRouter(prefix="/player/profile", tags=["player-profile"])

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
    400: openapi_error_examples(
        "Invalid or missing profile fields",
        examples={
            "empty_first_name": {
                "code": "VALIDATION_ERROR",
                "message": "First Name is required",
                "details": [{"field": "first_name", "message": "First Name is required"}],
            },
            "empty_last_name": {
                "code": "VALIDATION_ERROR",
                "message": "Last Name is required",
                "details": [{"field": "last_name", "message": "Last Name is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid phone number",
                "details": [{"field": "phone_number", "message": "Enter a valid phone number"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Duplicate email or username already used by another account",
        examples={
            "email_already_in_use": {
                "code": "EMAIL_ALREADY_IN_USE",
                "message": "This email is already in use by another account",
                "details": [
                    {
                        "field": "email",
                        "message": "This email is already in use by another account",
                    }
                ],
            },
            "username_already_in_use": {
                "code": "USERNAME_ALREADY_IN_USE",
                "message": "This username is already in use by another account",
                "details": [
                    {
                        "field": "username",
                        "message": "This username is already in use by another account",
                    }
                ],
            },
        },
    ),
}


@router.get(
    "",
    response_model=PlayerProfileResponse,
    operation_id="getPlayerProfile",
    summary="Get current player profile",
    description=(
        "Return the authenticated player's profile for the **Edit Profile** screen.\n\n"
        "Includes `first_name`, `last_name`, `email`, `username`, `phone_number`, "
        "`date_of_birth`, `gender`, `grade`, `parent_guardian`, nested `profile` data, "
        "and mobile envelope fields (`title`, `name`, `avatar`, `status`, `description`).\n\n"
        "Optional `phone` in update requests is client metadata and is not persisted.\n\n"
        "**Requires authenticated player JWT** (`Authorization: Bearer <access_token>`)."
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
async def get_player_profile(
    current_user: User = Depends(get_current_player),
) -> PlayerProfileResponse:
    result = player_profile_service.build_player_profile_response(
        current_user,
        message="Profile loaded successfully",
        description="Review and update your personal information",
    )
    return PlayerProfileResponse(**result)


@router.put(
    "",
    response_model=PlayerProfileResponse,
    operation_id="updatePlayerProfile",
    summary="Update current player profile",
    description=(
        "Update the authenticated player's profile.\n\n"
        "Required fields: `first_name`, `last_name`, `email`.\n\n"
        "Optional fields: `username`, `phone_number` (e.g. `+1 (555) 382-9102`), "
        "`date_of_birth` (MM/DD/YYYY), `gender`, `grade`, `parent_guardian`, and client "
        "`phone` metadata.\n\n"
        "Returns **400** for empty required fields, invalid email format, or invalid phone format.\n\n"
        "Returns **409** when the email or username is already used by another account.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_player_profile(
    body: PlayerProfileUpdateRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerProfileResponse:
    updated_user = await player_profile_service.update_player_profile(db, current_user, body)
    result = player_profile_service.build_player_profile_response(
        updated_user,
        message="Profile updated successfully",
        description="Your profile changes have been saved",
        status="saved",
    )
    return PlayerProfileResponse(**result)
