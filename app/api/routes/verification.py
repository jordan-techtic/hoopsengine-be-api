"""Authenticated email verification endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ResendVerificationCodeRequest,
    ResendVerificationCodeResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.services import email_verification as email_verification_service

router = APIRouter(tags=["auth"])

VERIFY_SUCCESS_MESSAGE = "Email verified successfully."
VERIFY_DESCRIPTION = "Your email address has been confirmed."
RESEND_SUCCESS_MESSAGE = "A new verification code has been sent to your email."

AUTH_ERROR_RESPONSES = {
    403: openapi_error(
        "Missing or invalid JWT (`FORBIDDEN`)",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid OTP, expired OTP, missing OTP, or unregistered email",
        examples={
            "invalid_otp": {
                "code": "INVALID_OTP",
                "message": "The verification code is incorrect",
                "details": [{"field": "otp_code", "message": "The verification code is incorrect"}],
            },
            "otp_expired": {
                "code": "OTP_EXPIRED",
                "message": "The verification code has expired. Please request a new code.",
                "details": [
                    {
                        "field": "otp_code",
                        "message": "The verification code has expired. Please request a new code.",
                    }
                ],
            },
            "missing_otp": {
                "code": "VALIDATION_ERROR",
                "message": "Verification code is required",
                "details": [{"field": "otp_code", "message": "Verification code is required"}],
            },
            "email_not_registered": {
                "code": "EMAIL_NOT_REGISTERED",
                "message": "We couldn't find an account with that email address",
                "details": [
                    {
                        "field": "email",
                        "message": "We couldn't find an account with that email address",
                    }
                ],
            },
        },
    ),
    422: openapi_error(
        "Request validation failed (invalid email format or OTP pattern)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "otp_code", "message": "String should match pattern '^\\d{6}$'"}],
    ),
}

ALREADY_VERIFIED_RESPONSE = {
    409: openapi_error(
        "Email already verified",
        code="EMAIL_ALREADY_VERIFIED",
        message="This email address has already been verified",
        details=[
            {
                "field": "email",
                "message": "This email address has already been verified",
            }
        ],
    ),
}

RESEND_COOLDOWN_RESPONSE = {
    429: openapi_error(
        "Resend requested too frequently",
        code="RESEND_COOLDOWN",
        message="Please wait before requesting another verification code",
        details=[
            {
                "field": "otp_code",
                "message": "Please wait before requesting another verification code",
            }
        ],
    ),
}


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    operation_id="verifyEmail",
    summary="Verify email with OTP code",
    description=(
        "Confirm the authenticated coach's email address using the 6-digit code "
        "sent during registration or resend.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Returns **200** on success with `status=verified`. Returns **400** for "
        "missing, invalid, or expired OTP codes. Returns **409** when the email "
        "is already verified. Returns **403** when the request is unauthenticated."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **ALREADY_VERIFIED_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def verify_email(
    payload: VerifyEmailRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyEmailResponse:
    """Verify the authenticated user's email using a 6-digit OTP."""
    user = await email_verification_service.verify_email_otp(
        db,
        current_user=current_user,
        otp_code=payload.otp_code,
        request_email=str(payload.email) if payload.email else None,
    )
    return VerifyEmailResponse(
        message=VERIFY_SUCCESS_MESSAGE,
        description=VERIFY_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/coach/dashboard",
        id=user.id,
        email=user.email,
    )


@router.post(
    "/resend-verification-code",
    response_model=ResendVerificationCodeResponse,
    operation_id="resendVerificationCode",
    summary="Resend email verification code",
    description=(
        "Send a new 6-digit verification code to the authenticated coach's "
        "registered email address.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Returns **200** on success. Returns **429** when resend is requested "
        "too frequently. Returns **409** when the email is already verified. "
        "Returns **400** when the supplied email is not registered. "
        "Returns **403** when the request is unauthenticated."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **ALREADY_VERIFIED_RESPONSE,
        **RESEND_COOLDOWN_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def resend_verification_code(
    payload: ResendVerificationCodeRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ResendVerificationCodeResponse:
    """Resend a verification OTP to the authenticated user's email."""
    user = await email_verification_service.resend_verification_code(
        db,
        current_user=current_user,
        request_email=str(payload.email) if payload.email else None,
    )
    return ResendVerificationCodeResponse(
        message=RESEND_SUCCESS_MESSAGE,
        description=f"We sent a 6-digit code to {user.email}",
        id=user.id,
        email=user.email,
    )
