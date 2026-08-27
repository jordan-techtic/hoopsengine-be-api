"""Coach authentication endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.auth import (
    CoachForgotPasswordRequest,
    CoachForgotPasswordResponse,
    CoachLoginRequest,
    CoachLoginResponse,
)
from app.schemas.errors import openapi_error
from app.services import auth as auth_service

router = APIRouter(prefix="/coach", tags=["coach-auth"])

FORGOT_PASSWORD_SUCCESS_MESSAGE = "Password reset link has been sent to your email."
FORGOT_PASSWORD_DESCRIPTION = "Check your inbox for instructions to reset your password."

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing email/username or password, or empty password",
        code="VALIDATION_ERROR",
        message="Password is required",
        details=[{"field": "password", "message": "Password is required"}],
    ),
    422: openapi_error(
        "Request validation failed (invalid email format on forgot-password)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "email", "message": "value is not a valid email address"}],
    ),
}

INVALID_CREDENTIALS_RESPONSE = {
    401: openapi_error(
        "Invalid email/username or password",
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error(
        "Coach account not found for forgot-password email",
        code="USER_NOT_FOUND",
        message="We couldn't find an account with that email. Please check the email address and try again.",
    ),
}


def _validate_coach_login_payload(payload: CoachLoginRequest) -> None:
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


@router.post(
    "/login",
    response_model=CoachLoginResponse,
    operation_id="coachLogin",
    summary="Coach login",
    description=(
        "Authenticate a verified coach using an email address or username and password.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Returns **200** with a JWT on success. Set `remember_me=true` for a longer-lived "
        "token (`REMEMBER_ME_TOKEN_EXPIRE_HOURS`). Returns **401** for invalid credentials "
        "or unverified email. Returns **400** when email/username or password is missing."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **INVALID_CREDENTIALS_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def coach_login(
    payload: CoachLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> CoachLoginResponse:
    """Authenticate a coach and return a JWT access token."""
    _validate_coach_login_payload(payload)
    result = await auth_service.login_coach(
        db,
        payload.email.strip(),
        payload.password,
        remember_me=payload.remember_me,
    )
    if result is None:
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )
    return result


@router.post(
    "/forgot-password",
    response_model=CoachForgotPasswordResponse,
    operation_id="coachForgotPassword",
    summary="Coach forgot password",
    description=(
        "Initiate the password recovery process for a coach account.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Sends a password reset link to the coach's registered email. Returns **404** "
        "when no matching coach account exists. The response includes a `link` to the "
        "password reset page for the Forgot Password UI flow."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def coach_forgot_password(
    payload: CoachForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> CoachForgotPasswordResponse:
    """Send a password reset email to the coach account."""
    reset_token = await auth_service.request_coach_password_reset(db, str(payload.email))
    if reset_token is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="We couldn't find an account with that email. Please check the email address and try again.",
            status_code=404,
        )

    response = CoachForgotPasswordResponse(
        message=FORGOT_PASSWORD_SUCCESS_MESSAGE,
        description=FORGOT_PASSWORD_DESCRIPTION,
        link=settings.RESET_PASSWORD_URL,
    )
    if settings.DEBUG:
        response.reset_token = reset_token
    return response
