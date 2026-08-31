"""Organization admin reset password endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ResetPasswordFormResponse,
    ValidatePasswordStrengthResponse,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_reset_password import OrgAdminResetPasswordRequest
from app.services import password_reset as password_reset_service

router = APIRouter(prefix="/admin/reset-password", tags=["org-admin-reset-password"])

RESET_SUCCESS_MESSAGE = "Password has been reset successfully."
RESET_DESCRIPTION = "Your new password is now active. Use it the next time you sign in."
VALIDATE_VALID_MESSAGE = "Password meets all strength requirements."
VALIDATE_INVALID_MESSAGE = "Password does not meet all strength requirements."

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Empty password, weak password, or password confirmation mismatch",
        examples={
            "empty_password": {
                "code": "VALIDATION_ERROR",
                "message": "New password is required",
                "details": [{"field": "new_password", "message": "New password is required"}],
            },
            "weak_password": {
                "code": "VALIDATION_ERROR",
                "message": "Password must be at least 8 characters",
                "details": [{"field": "password", "message": "Password must be at least 8 characters"}],
            },
            "missing_uppercase": {
                "code": "VALIDATION_ERROR",
                "message": "Password must include at least one uppercase letter",
                "details": [
                    {
                        "field": "password",
                        "message": "Password must include at least one uppercase letter",
                    }
                ],
            },
            "missing_number": {
                "code": "VALIDATION_ERROR",
                "message": "Password must include at least one number",
                "details": [{"field": "password", "message": "Password must include at least one number"}],
            },
            "missing_special": {
                "code": "VALIDATION_ERROR",
                "message": "Password must include at least one special character",
                "details": [
                    {
                        "field": "password",
                        "message": "Password must include at least one special character",
                    }
                ],
            },
            "password_mismatch": {
                "code": "VALIDATION_ERROR",
                "message": "Passwords do not match",
                "details": [{"field": "confirm_password", "message": "Passwords do not match"}],
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
    status_code=status.HTTP_200_OK,
    operation_id="resetOrgAdminPassword",
    summary="Reset organization admin password",
    description=(
        "Reset the authenticated organization admin's password using a new password "
        "and confirmation.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Accepts Figma fields `new_password`, `confirm_password`, and optional client "
        "metadata `phone` (not persisted unless non-empty).\n\n"
        "Returns **200** on success. Returns **400** when passwords are empty, do not match, "
        "or fail strength requirements (minimum 8 characters, uppercase, lowercase, number, "
        "and special character). Returns **403** when the caller is not an organization admin. "
        "Returns **409** when the new password is the same as the current password."
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
async def reset_org_admin_password(
    body: OrgAdminResetPasswordRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordFormResponse:
    """Reset the authenticated organization admin's password."""
    user = await password_reset_service.reset_authenticated_password(
        db,
        user=current_user,
        new_password=body.new_password,
        confirm_password=body.confirm_password,
        phone=body.phone,
    )
    return ResetPasswordFormResponse(
        message=RESET_SUCCESS_MESSAGE,
        description=RESET_DESCRIPTION,
        link=f"{settings.FRONTEND_URL.rstrip('/')}/organization/login",
        id=user.id,
    )


@router.get(
    "/validate",
    response_model=ValidatePasswordStrengthResponse,
    operation_id="validateOrgAdminPasswordStrength",
    summary="Validate organization admin new password strength",
    description=(
        "Evaluate whether a candidate password meets strength requirements for the "
        "Organization Admin **Reset Password** screen strength indicator and checklist.\n\n"
        "**Requires organization admin JWT**.\n\n"
        "Provide the Figma **Password Strength** field as the `password` query parameter. "
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **200** with requirement checklist fields (`min_length`, `has_number`, "
        "`has_special`, etc.) and `status=valid` or `status=invalid`. Returns **400** when "
        "the `password` query parameter is missing or empty. Returns **403** when the caller "
        "is not an organization admin."
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
async def validate_org_admin_password_strength(
    password: str | None = Query(
        default=None,
        description="Candidate password to evaluate (Figma Password Strength field)",
        examples=["StrongPassword123!"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional phone metadata from the status bar (Figma field)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_org_admin),
) -> ValidatePasswordStrengthResponse:
    """Return password strength checklist for the org-admin Reset Password UI."""
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
