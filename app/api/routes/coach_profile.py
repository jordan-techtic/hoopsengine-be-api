"""Authenticated user profile endpoints for the Edit Profile screen."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.profile import CoachProfileResponse, CoachProfileUpdateRequest
from app.services import profile as profile_service

router = APIRouter(prefix="/profile", tags=["coach-profile"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid or missing profile fields",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "first_name", "message": "First name is required"}],
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
    response_model=CoachProfileResponse,
    operation_id="getCoachProfile",
    summary="Get current user profile",
    description=(
        "Return the authenticated user's profile for the **Edit Profile** screen.\n\n"
        "Includes `first_name`, `last_name`, `email`, `username`, `phone_number`, "
        "`date_of_birth`, `gender`, `grade`, `parent_guardian`, and nested `profile` data.\n\n"
        "Optional `phone` in update requests is client metadata and is not persisted.\n\n"
        "**Requires authenticated JWT** (`Authorization: Bearer <access_token>`)."
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
async def get_coach_profile(
    current_user: User = Depends(get_current_user),
) -> CoachProfileResponse:
    result = profile_service.build_coach_profile_response(
        current_user,
        message="Profile loaded successfully",
        description="Review and update your personal information",
    )
    return CoachProfileResponse(**result)


@router.put(
    "",
    response_model=CoachProfileResponse,
    operation_id="updateCoachProfile",
    summary="Update current user profile",
    description=(
        "Update the authenticated user's profile.\n\n"
        "Required fields: `first_name`, `last_name`, `email`.\n\n"
        "Optional fields: `username`, `phone_number`, `date_of_birth` (MM/DD/YYYY), "
        "`gender`, `grade`, `parent_guardian`, and client `phone` metadata.\n\n"
        "Returns **400** for empty required fields, invalid email format, or invalid phone format.\n\n"
        "Returns **409** when the email or username is already used by another account.\n\n"
        "**Requires authenticated JWT**."
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
async def update_coach_profile(
    body: CoachProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CoachProfileResponse:
    updated_user = await profile_service.update_coach_profile(db, current_user, body)
    result = profile_service.build_coach_profile_response(
        updated_user,
        message="Profile updated successfully",
        description="Your profile changes have been saved",
        status="saved",
    )
    return CoachProfileResponse(**result)
