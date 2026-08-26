from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_bearer_token, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
    ValidateResetTokenRequest,
    ValidateResetTokenResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

FORGOT_PASSWORD_SUCCESS_MESSAGE = "Password reset link has been sent to your email."


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Authenticate with email and password. Returns a JWT access token.",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    result = await auth_service.login_user(db, payload.email, payload.password)
    if result is None:
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )
    return result


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Invalidate the current user session. Available for all roles.",
)
async def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(get_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout_user(db, token, current_user.id)
    return MessageResponse(message="Logged out successfully")


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Forgot password",
    description="Request a password reset token for the given email.",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    reset_token = await auth_service.request_password_reset(db, payload.email)
    if reset_token is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="We couldn't find an account with that email. Please check the email address and try again.",
            status_code=404,
        )

    response = ForgotPasswordResponse(message=FORGOT_PASSWORD_SUCCESS_MESSAGE)
    if settings.DEBUG:
        response.reset_token = reset_token
    return response


@router.post(
    "/validate-reset-token",
    response_model=ValidateResetTokenResponse,
    summary="Validate reset token",
    description=(
        "Check whether the reset password token from the email link is valid "
        "before showing the reset password form."
    ),
)
async def validate_reset_token(
    payload: ValidateResetTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidateResetTokenResponse:
    user = await auth_service.validate_reset_token(db, payload.token)
    if user is None:
        return ValidateResetTokenResponse(
            valid=False,
            message="This reset link is invalid or has expired. Please request a new password reset.",
        )

    return ValidateResetTokenResponse(
        valid=True,
        message="Reset link is valid. You can set a new password.",
        email=user.email,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password",
    description="Set a new password using the reset token from forgot-password.",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    updated = await auth_service.reset_password(db, payload.token, payload.new_password)
    if not updated:
        raise AppException(
            code="INVALID_RESET_TOKEN",
            message="Invalid or expired reset token",
            status_code=400,
        )
    return MessageResponse(message="Password has been reset successfully")
