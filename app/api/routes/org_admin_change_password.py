"""Organization admin change password ticket-path endpoint (HE-410)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_change_password import (
    OrgAdminChangePasswordRequest,
    OrgAdminChangePasswordResponse,
)
from app.services import org_admin_profile as org_admin_profile_service

router = APIRouter(prefix="/admin/change-password", tags=["org-admin-change-password"])

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

CHANGE_PASSWORD_VALIDATION_RESPONSES = {
    400: openapi_error_examples(
        "Empty password, incorrect current password, weak password, or confirmation mismatch",
        examples={
            "empty_current_password": {
                "code": "VALIDATION_ERROR",
                "message": "Current password is required",
                "details": [{"field": "current_password", "message": "Current password is required"}],
            },
            "incorrect_current_password": {
                "code": "VALIDATION_ERROR",
                "message": "Current password is incorrect",
                "details": [{"field": "current_password", "message": "Current password is incorrect"}],
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
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CHANGE_PASSWORD_CONFLICT_RESPONSES = {
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


@router.post(
    "",
    response_model=OrgAdminChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    operation_id="changeOrgAdminPasswordAdminPath",
    summary="Change organization admin password (admin path)",
    description=(
        "Change the authenticated organization admin's password using the current password, "
        "new password, and confirmation.\n\n"
        "Ticket path alias for the Organization Admin **Change Password** screen "
        "(HE-410). Behavior matches POST /organization/change-password.\n\n"
        "Accepts Figma fields `current_password`, `new_password`, `confirm_password`, "
        "optional client metadata `phone` (not persisted), and optional write-only `password` "
        "alias for `confirm_password`.\n\n"
        "Returns **200** on success with `success`, `message`, `status`, `description`, `id`, "
        "`phone`, and `password` (always null). Returns **400** when passwords are empty, the "
        "current password is incorrect, confirmation does not match, or the new password fails "
        "strength requirements (minimum 8 characters with uppercase, lowercase, number, and "
        "special character). Returns **403** when the caller is not an organization admin. "
        "Returns **409** when the new password matches the current password.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **CHANGE_PASSWORD_VALIDATION_RESPONSES,
        **CHANGE_PASSWORD_CONFLICT_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def change_org_admin_password_admin_path(
    body: OrgAdminChangePasswordRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminChangePasswordResponse:
    """Change password from the Organization Admin Change Password screen (HE-410)."""
    user = await org_admin_profile_service.change_org_admin_password(db, current_user, body)
    return OrgAdminChangePasswordResponse(
        message="Password changed successfully",
        description="Your new password is now active",
        id=user.id,
        phone=body.phone,
    )
