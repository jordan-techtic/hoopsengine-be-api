"""Player authentication endpoints for password recovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_auth import (
    PlayerForgotPasswordRequest,
    PlayerForgotPasswordResponse,
    PlayerInvitationVerifyResponse,
    PlayerResetPasswordRequest,
    PlayerResetPasswordResponse,
    PlayerVerifyCodeRequest,
    PlayerVerifyCodeResponse,
)
from app.services import player_invitation as player_invitation_service
from app.services import player_recovery as player_recovery_service
from app.services import player_reset_password as player_reset_password_service

router = APIRouter(prefix="/player", tags=["player-auth"])

FORGOT_PASSWORD_SUCCESS_MESSAGE = "A verification code has been sent to your email."
FORGOT_PASSWORD_DESCRIPTION = (
    "Check your inbox for the 6-digit verification code to reset your password."
)
VERIFY_SUCCESS_MESSAGE = "Verification code confirmed. You can now reset your password."
VERIFY_PASSWORD_RESET_MESSAGE = "Your password has been reset successfully."
VERIFY_DESCRIPTION = "Enter and confirm your new password to complete the reset."
VERIFY_PASSWORD_RESET_DESCRIPTION = "Your new password is now active. Use it the next time you sign in."

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid email, verification code, or password fields",
        examples={
            "email_required": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "invalid_verification_code": {
                "code": "INVALID_VERIFICATION_CODE",
                "message": "The verification code is incorrect",
                "details": [
                    {
                        "field": "verification_code",
                        "message": "The verification code is incorrect",
                    }
                ],
            },
            "weak_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password must be at least 8 characters",
                "details": [{"field": "password", "message": "Password must be at least 8 characters"}],
            },
            "password_mismatch": {
                "code": "VALIDATION_ERROR",
                "message": "Passwords do not match",
                "details": [{"field": "confirm_password", "message": "Passwords do not match"}],
            },
        },
    ),
    422: openapi_error(
        "Request validation failed (invalid field types)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_RESPONSE = {
    404: openapi_error_examples(
        "Player account or invitation code not found",
        examples={
            "recovery_email_not_found": {
                "code": "USER_NOT_FOUND",
                "message": "We couldn't find an account with that email. Please check the email address and try again.",
                "details": [
                    {
                        "field": "email",
                        "message": "We couldn't find an account with that email. Please check the email address and try again.",
                    }
                ],
            },
            "invitation_not_found": {
                "code": "INVITATION_CODE_NOT_FOUND",
                "message": "We couldn't find a player invitation with that code",
                "details": [
                    {
                        "field": "invitation_code",
                        "message": "We couldn't find a player invitation with that code",
                    }
                ],
            },
        },
    ),
}

INVITATION_CONFLICT_RESPONSE = {
    409: openapi_error(
        "Invitation code has already been redeemed",
        code="INVITATION_ALREADY_REDEEMED",
        message="This invitation code has already been used",
        details=[
            {
                "field": "invitation_code",
                "message": "This invitation code has already been used",
            }
        ],
    ),
}

EXPIRED_CODE_RESPONSE = {
    403: openapi_error(
        "Recovery verification code has expired",
        code="RECOVERY_CODE_EXPIRED",
        message="The verification code has expired. Please request a new code.",
        details=[
            {
                "field": "verification_code",
                "message": "The verification code has expired. Please request a new code.",
            }
        ],
    ),
}

RESEND_COOLDOWN_RESPONSE = {
    429: openapi_error(
        "Recovery code requested too frequently",
        code="RESEND_COOLDOWN",
        message="Please wait before requesting another verification code",
    ),
}

RESET_PASSWORD_AUTH_RESPONSES = {
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

RESET_PASSWORD_VALIDATION_RESPONSES = {
    400: openapi_error_examples(
        "Empty password, weak password, or password confirmation mismatch",
        examples={
            "empty_new_password": {
                "code": "VALIDATION_ERROR",
                "message": "New password is required",
                "details": [{"field": "new_password", "message": "New password is required"}],
            },
            "weak_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password must be at least 8 characters",
                "details": [{"field": "password", "message": "Password must be at least 8 characters"}],
            },
            "password_mismatch": {
                "code": "VALIDATION_ERROR",
                "message": "Passwords do not match",
                "details": [{"field": "confirm_password", "message": "Passwords do not match"}],
            },
        },
    ),
    422: openapi_error(
        "Request validation failed (invalid field types)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

RESET_PASSWORD_CONFLICT_RESPONSE = {
    409: openapi_error(
        "New password matches the current password",
        code="PASSWORD_UNCHANGED",
        message="New password must be different from your current password",
        details=[
            {
                "field": "new_password",
                "message": "New password must be different from your current password",
            }
        ],
    ),
}

RESET_SUCCESS_MESSAGE = "Password has been reset successfully."
RESET_DESCRIPTION = "Your new password is now active. Use it the next time you sign in."


def _player_login_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/player/login"


@router.post(
    "/forgot-password",
    response_model=PlayerForgotPasswordResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playerForgotPassword",
    summary="Player forgot password",
    description=(
        "Initiate player password recovery by sending a 6-digit verification code to the "
        "registered email address.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Accepts `email` (required) and optional client `phone` metadata (not persisted).\n\n"
        "Returns **201** when the recovery code is sent. Returns **400** when the email is "
        "empty or invalid. Returns **404** when no matching player account exists. Returns "
        "**429** when a new code is requested before the resend cooldown elapses."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
        **RESEND_COOLDOWN_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def player_forgot_password(
    payload: PlayerForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> PlayerForgotPasswordResponse:
    """Send a password recovery verification code to the player account email."""
    user, otp_code = await player_recovery_service.request_player_password_recovery(
        db,
        payload.email,
    )
    response = PlayerForgotPasswordResponse(
        message=FORGOT_PASSWORD_SUCCESS_MESSAGE,
        description=FORGOT_PASSWORD_DESCRIPTION,
        link=settings.PLAYER_RESET_PASSWORD_URL,
        email=user.email,
    )
    if settings.DEBUG:
        response.verification_code = otp_code
    return response


def _player_login_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/player/login"


def _is_invitation_verify_payload(payload: PlayerVerifyCodeRequest) -> bool:
    return bool((payload.invitation_code or "").strip())


def _is_recovery_verify_payload(payload: PlayerVerifyCodeRequest) -> bool:
    return bool((payload.email or "").strip()) or bool((payload.verification_code or "").strip())


@router.post(
    "/verify-code",
    response_model=PlayerInvitationVerifyResponse | PlayerVerifyCodeResponse,
    operation_id="playerVerifyCode",
    summary="Verify player invitation or recovery code",
    description=(
        "Verify a player invitation code **or** a password recovery OTP.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "**Invitation verification:** submit `invitation_code` in `PC-XXXXXXXX` format "
        "(case sensitive). Returns **201** on success with player and organization metadata.\n\n"
        "**Password recovery:** submit `email` and `verification_code` (6-digit OTP). Optionally "
        "include `password` and `confirm_password` to reset the password in the same step. "
        "Returns **200** when the recovery code is valid.\n\n"
        "Optional client `phone` metadata is accepted but not persisted.\n\n"
        "Returns **400** for empty or invalid invitation codes, or recovery validation failures. "
        "Returns **404** when the invitation or email is not found. Returns **409** when an "
        "invitation code was already redeemed. Returns **403** when a recovery code has expired."
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSE,
        **INVITATION_CONFLICT_RESPONSE,
        **EXPIRED_CODE_RESPONSE,
        201: {
            "description": "Invitation code verified successfully",
            "model": PlayerInvitationVerifyResponse,
        },
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def player_verify_code(
    payload: PlayerVerifyCodeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> PlayerInvitationVerifyResponse | PlayerVerifyCodeResponse:
    """Verify a player invitation code or password recovery OTP."""
    if _is_invitation_verify_payload(payload):
        if _is_recovery_verify_payload(payload):
            raise AppException(
                code="VALIDATION_ERROR",
                message="Provide either invitation_code or email with verification_code, not both",
                status_code=400,
                details=[
                    {
                        "field": "invitation_code",
                        "message": "Provide either invitation_code or email with verification_code, not both",
                    }
                ],
            )
        result = await player_invitation_service.verify_player_invitation_code(
            db,
            payload.invitation_code or "",
        )
        response.status_code = status.HTTP_201_CREATED
        return PlayerInvitationVerifyResponse(**result)

    if not _is_recovery_verify_payload(payload):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invitation code is required",
            status_code=400,
            details=[{"field": "invitation_code", "message": "Invitation code is required"}],
        )

    password_provided = payload.password is not None or payload.confirm_password is not None
    user = await player_recovery_service.verify_player_recovery_code(
        db,
        email=payload.email or "",
        verification_code=payload.verification_code,
        password=payload.password,
        confirm_password=payload.confirm_password,
    )
    if password_provided:
        message = VERIFY_PASSWORD_RESET_MESSAGE
        description = VERIFY_PASSWORD_RESET_DESCRIPTION
        status_value = "password_reset"
    else:
        message = VERIFY_SUCCESS_MESSAGE
        description = VERIFY_DESCRIPTION
        status_value = "verified"

    response.status_code = status.HTTP_200_OK
    return PlayerVerifyCodeResponse(
        message=message,
        description=description,
        link=settings.PLAYER_RESET_PASSWORD_URL,
        email=user.email,
        id=user.id,
        status=status_value,
    )


@router.post(
    "/reset-password",
    response_model=PlayerResetPasswordResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playerResetPassword",
    summary="Reset authenticated player password",
    description=(
        "Reset the authenticated player's password using a new password and confirmation.\n\n"
        "**Requires authenticated player JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Required fields: `new_password`, `confirm_password`. Optional client `phone` and "
        "`password` (Password Strength UI echo) metadata are accepted but not persisted.\n\n"
        "Returns **201** on success with a confirmation message. Returns **400** when passwords "
        "are empty, do not match, or fail strength requirements (minimum 8 characters, "
        "uppercase, lowercase, number, and special character). Returns **401** when "
        "unauthenticated. Returns **403** when the caller is not a player. Returns **409** when "
        "the new password is the same as the current password."
    ),
    responses={
        **RESET_PASSWORD_AUTH_RESPONSES,
        **RESET_PASSWORD_VALIDATION_RESPONSES,
        **RESET_PASSWORD_CONFLICT_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def player_reset_password(
    payload: PlayerResetPasswordRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerResetPasswordResponse:
    """Reset the authenticated player's password."""
    user = await player_reset_password_service.reset_player_password(
        db,
        user=current_user,
        new_password=payload.new_password,
        confirm_password=payload.confirm_password,
    )
    return PlayerResetPasswordResponse(
        message=RESET_SUCCESS_MESSAGE,
        description=RESET_DESCRIPTION,
        link=_player_login_link(),
        id=user.id,
    )
