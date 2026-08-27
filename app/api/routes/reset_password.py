"""Authenticated reset password endpoints for the Coach module."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ResetPasswordFormRequest,
    ResetPasswordFormResponse,
    ValidatePasswordStrengthResponse,
)
from app.schemas.errors import openapi_error
from app.services import password_reset as password_reset_service

router = APIRouter(prefix="/reset-password", tags=["reset-password"])

RESET_SUCCESS_MESSAGE = "Password has been reset successfully."
RESET_DESCRIPTION = "Your new password is now active. Use it the next time you sign in."
VALIDATE_VALID_MESSAGE = "Password meets all strength requirements."
VALIDATE_INVALID_MESSAGE = "Password does not meet all strength requirements."

AUTH_ERROR_RESPONSES = {
    403: openapi_error(
        "Missing or invalid JWT (`FORBIDDEN`)",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Empty password, weak password, or password confirmation mismatch",
        code="VALIDATION_ERROR",
        message="Password must be at least 8 characters",
        details=[{"field": "password", "message": "Password must be at least 8 characters"}],
    ),
    422: openapi_error(
        "Request validation failed (invalid field types)",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
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


def _strength_label(requirements: dict[str, bool]) -> str:
    met = sum(1 for value in requirements.values() if value)
    if met == len(requirements):
        return "strong"
    if met >= 3:
        return "medium"
    return "weak"


@router.post(
    "",
    response_model=ResetPasswordFormResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="resetPasswordForm",
    summary="Reset authenticated user password",
    description=(
        "Reset the authenticated coach's password using a new password and confirmation.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Returns **201** on success. Returns **400** when passwords are empty, do not match, "
        "or fail strength requirements (minimum 8 characters, uppercase, lowercase, number, "
        "and special character). Returns **403** when unauthenticated. Returns **409** when "
        "the new password is the same as the current password."
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
async def reset_password_form(
    payload: ResetPasswordFormRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordFormResponse:
    """Reset the authenticated user's password."""
    user = await password_reset_service.reset_authenticated_password(
        db,
        user=current_user,
        new_password=payload.new_password,
        confirm_password=payload.confirm_password,
        phone=payload.phone,
    )
    return ResetPasswordFormResponse(
        message=RESET_SUCCESS_MESSAGE,
        description=RESET_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/coach/login",
        id=user.id,
    )


@router.get(
    "/validate",
    response_model=ValidatePasswordStrengthResponse,
    operation_id="validatePasswordStrength",
    summary="Validate new password strength",
    description=(
        "Evaluate whether a candidate password meets strength requirements for the "
        "Reset Password screen strength indicator and checklist.\n\n"
        "**Requires Bearer JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Returns **200** with requirement checklist fields (`min_length`, `has_number`, "
        "`has_special`, etc.) and `status=valid` or `status=invalid`. Returns **400** when "
        "the `password` query parameter is missing or empty. Returns **403** when "
        "unauthenticated."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def validate_password_strength(
    password: str | None = Query(
        default=None,
        description="Candidate password to evaluate for the strength indicator",
        examples=["StrongPassword123!"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional phone metadata from the status bar (Figma field)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(require_authenticated_user),
) -> ValidatePasswordStrengthResponse:
    """Return password strength checklist for the Reset Password UI."""
    requirements, is_valid = password_reset_service.validate_password_for_reset(password)

    return ValidatePasswordStrengthResponse(
        message=VALIDATE_VALID_MESSAGE if is_valid else VALIDATE_INVALID_MESSAGE,
        description="Password strength requirements for a secure account.",
        status="valid" if is_valid else "invalid",
        strength=_strength_label(requirements),
        requirements=requirements,
        id=current_user.id,
        phone=phone,
    )
