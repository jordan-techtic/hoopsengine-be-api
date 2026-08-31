"""Player login endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_auth import (
    PlayerLoginRequest,
    PlayerLoginResponse,
    PlayerLoginValidateResponse,
)
from app.services import player_auth as player_auth_service

router = APIRouter(prefix="/login", tags=["player-auth"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing email/username or password, or invalid email format",
        examples={
            "missing_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email or username is required",
                "details": [{"field": "email", "message": "Email or username is required"}],
            },
            "missing_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password is required",
                "details": [{"field": "password", "message": "Password is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
        },
    ),
    422: openapi_error(
        "Request validation failed (invalid field types)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

INVALID_CREDENTIALS_RESPONSE = {
    401: openapi_error(
        "Invalid email/username or password",
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
    ),
}

DUPLICATE_SESSION_RESPONSE = {
    409: openapi_error(
        "An active session already exists for this account",
        code="DUPLICATE_SESSION",
        message="You are already signed in on this account",
        details=[
            {
                "field": "email",
                "message": "An active session already exists. Sign out before signing in again.",
            }
        ],
    ),
}


def _validate_player_login_payload(payload: PlayerLoginRequest) -> None:
    """Raise 400 when required login fields are missing or empty."""
    if payload.email is None or not payload.email.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email or username is required",
            status_code=400,
            details=[{"field": "email", "message": "Email or username is required"}],
        )
    if payload.password is None or not payload.password.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password is required",
            status_code=400,
            details=[{"field": "password", "message": "Password is required"}],
        )

    format_errors = player_auth_service.validate_identifier_format(payload.email)
    if format_errors:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=format_errors,
        )


@router.post(
    "",
    response_model=PlayerLoginResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playerLogin",
    summary="Player login",
    description=(
        "Authenticate a verified player using an email address or username and password.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Accepts `email` (email or username), `password`, optional `remember_me`, and optional "
        "client `phone` metadata (not persisted).\n\n"
        "Returns **201** with a JWT on success. Set `remember_me=true` for a longer-lived token "
        "(`REMEMBER_ME_TOKEN_EXPIRE_HOURS`). Returns **400** when email/username or password is "
        "missing or the email format is invalid. Returns **401** for invalid credentials. "
        "Returns **409** when an active session already exists for the account."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **INVALID_CREDENTIALS_RESPONSE,
        **DUPLICATE_SESSION_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def player_login(
    payload: PlayerLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> PlayerLoginResponse:
    """Authenticate a player and return a JWT access token."""
    _validate_player_login_payload(payload)
    return await player_auth_service.login_player(
        db,
        payload.email.strip(),
        payload.password,
        remember_me=payload.remember_me,
    )


@router.get(
    "/validate",
    response_model=PlayerLoginValidateResponse,
    operation_id="playerLoginValidate",
    summary="Validate player login fields",
    description=(
        "Validate player login input for presence and email format before form submission.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Query parameters: `email` (email or username) and `password`.\n\n"
        "Returns **200** with `valid=true` when both fields pass validation, or `valid=false` "
        "with field-level `errors` when validation fails."
    ),
    responses={
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def player_login_validate(
    email: str | None = Query(
        default=None,
        description="Player email address or username to validate",
        examples=["player@example.com"],
    ),
    password: str | None = Query(
        default=None,
        description="Account password to validate for presence",
        examples=["StrongPassword123!"],
    ),
) -> PlayerLoginValidateResponse:
    """Validate login field presence and email format for the Player Login screen."""
    result = player_auth_service.validate_login_fields(email=email, password=password)
    return PlayerLoginValidateResponse(**result)
