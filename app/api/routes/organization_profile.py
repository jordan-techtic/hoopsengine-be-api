"""Organization admin profile endpoints."""

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
from app.schemas.org_admin_profile import (
    OrganizationProfileResponse,
    OrganizationProfileUpdateRequest,
)
from app.services import org_admin_profile as org_admin_profile_service

router = APIRouter(prefix="/organization", tags=["org-admin-profile"])

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
        "Missing or invalid profile fields",
        examples={
            "missing_organization_name": {
                "code": "VALIDATION_ERROR",
                "message": "Organization name is required",
                "details": [
                    {
                        "field": "organization_name",
                        "message": "Organization name is required",
                    }
                ],
            },
            "missing_name": {
                "code": "VALIDATION_ERROR",
                "message": "Organization name is required",
                "details": [{"field": "name", "message": "Organization name is required"}],
            },
            "missing_description": {
                "code": "VALIDATION_ERROR",
                "message": "Organization description is required",
                "details": [
                    {"field": "description", "message": "Organization description is required"}
                ],
            },
            "invalid_contact_info": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address or phone number",
                "details": [
                    {
                        "field": "contact_info",
                        "message": "Enter a valid email address or phone number",
                    }
                ],
            },
            "missing_first_name": {
                "code": "VALIDATION_ERROR",
                "message": "First Name is required",
                "details": [{"field": "first_name", "message": "First Name is required"}],
            },
            "missing_last_name": {
                "code": "VALIDATION_ERROR",
                "message": "Last Name is required",
                "details": [{"field": "last_name", "message": "Last Name is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
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
        "Duplicate organization name or email",
        examples={
            "organization_name_exists": {
                "code": "ORGANIZATION_NAME_EXISTS",
                "message": "An organization with this name already exists",
                "details": [
                    {
                        "field": "organization_name",
                        "message": "An organization with this name already exists",
                    }
                ],
            },
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
        },
    ),
}

NOT_FOUND_RESPONSES = {
    404: openapi_error(
        "Organization profile not found for the authenticated admin",
        code="ORGANIZATION_NOT_FOUND",
        message="Organization profile not found",
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


@router.get(
    "/profile",
    response_model=OrganizationProfileResponse,
    operation_id="getOrganizationProfile",
    summary="Get organization profile",
    description=(
        "Retrieve the current organization profile for the authenticated organization admin.\n\n"
        "Returns organization name, description, contact information, address, contact email, "
        "phone number, and the admin's first and last name.\n\n"
        "The management form fields are exposed as `name`, `organization_description`, and "
        "`contact_info`.\n\n"
        "Returns **404** when the admin account is not linked to an organization.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_organization_profile(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationProfileResponse:
    """Return organization profile details for the Edit Organization Profile screen."""
    payload = await org_admin_profile_service.get_organization_profile(db, current_user)
    return OrganizationProfileResponse(**payload)


@router.put(
    "/profile",
    response_model=OrganizationProfileResponse,
    operation_id="updateOrganizationProfile",
    summary="Update organization profile",
    description=(
        "Update the organization profile with validated fields.\n\n"
        "Supports two payload shapes:\n"
        "1. **Organization Profile Management** — required `name`, `description`, and "
        "`contact_info` (valid email or phone).\n"
        "2. **Edit Organization Profile (detailed form)** — required `organization_name`, "
        "`address`, `email`, `phone_number`, `first_name`, and `last_name`. Optional `phone` "
        "is client metadata and is not persisted.\n\n"
        "Returns **200** on success with a confirmation message. Returns **400** when required "
        "fields are missing or contact information is invalid. Returns **409** when the "
        "organization name or email already exists on another record. Returns **404** when no "
        "organization is linked.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_organization_profile(
    body: OrganizationProfileUpdateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationProfileResponse:
    """Update organization profile from the Edit Organization Profile form."""
    payload = await org_admin_profile_service.update_organization_profile(
        db,
        current_user,
        body,
    )
    return OrganizationProfileResponse(**payload)


@router.post(
    "/change-password",
    response_model=OrgAdminChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    operation_id="changeOrgAdminPassword",
    summary="Change organization admin password",
    description=(
        "Change the authenticated organization admin's password using the current password, "
        "new password, and confirmation.\n\n"
        "Accepts Figma fields `new_password`, `confirm_password`, and optional client "
        "metadata `phone` (not persisted). Optional `password` is a write-only alias for "
        "`confirm_password`.\n\n"
        "Returns **200** on success. Returns **400** when passwords are empty, the current "
        "password is incorrect, confirmation does not match, or the new password fails "
        "strength requirements. Returns **403** when the caller is not an organization admin. "
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
async def change_org_admin_password(
    body: OrgAdminChangePasswordRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminChangePasswordResponse:
    """Change password from the Organization Admin Account Settings screen."""
    user = await org_admin_profile_service.change_org_admin_password(db, current_user, body)
    return OrgAdminChangePasswordResponse(
        message="Password changed successfully",
        description="Your new password is now active",
        id=user.id,
        phone=body.phone,
    )
