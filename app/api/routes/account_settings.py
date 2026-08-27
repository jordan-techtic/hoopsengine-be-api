"""Account Settings endpoints for the Coach module."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.account_settings import (
    AccountProfileUpdateRequest,
    AccountProfileUpdateResponse,
    AuthKeysRequest,
    AuthKeysResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    HelpSupportResponse,
    OrganizationSettingsRequest,
    OrganizationSettingsResponse,
    PushNotificationsRequest,
    PushNotificationsResponse,
    SupportSubmitRequest,
    SupportSubmitResponse,
)
from app.schemas.errors import openapi_error, openapi_error_examples
from app.services import account_settings as account_settings_service
from app.services import profile as profile_service

router = APIRouter(prefix="/account/settings", tags=["account-settings"])

AUTH_ERROR_RESPONSES = {
    403: openapi_error(
        "Missing or invalid JWT",
        code="FORBIDDEN",
        message="Authentication is required to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid or missing account settings fields",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "current_password", "message": "Current password is required"}],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Duplicate organization name, email, or password unchanged",
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
            "password_unchanged": {
                "code": "PASSWORD_UNCHANGED",
                "message": "New password must be different from your current password",
                "details": [
                    {
                        "field": "new_password",
                        "message": "New password must be different from your current password",
                    }
                ],
            },
            "invalid_inquiry_subject": {
                "code": "INVALID_INQUIRY_SUBJECT",
                "message": "Inquiry subject must be selected from the predefined options",
                "details": [
                    {
                        "field": "inquiry_subject",
                        "message": "Inquiry subject must be selected from the predefined options",
                    }
                ],
            },
        },
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Organization not found",
        code="ORGANIZATION_NOT_FOUND",
        message="Organization not found",
    ),
}


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    operation_id="changeAccountPassword",
    summary="Change authenticated user password",
    description=(
        "Change the authenticated user's password using the current and new password.\n\n"
        "Requires **Bearer JWT**. Returns **200** on success.\n\n"
        "Returns **400** when `current_password` is empty, incorrect, or the new password "
        "fails strength requirements.\n\n"
        "Returns **409** when the new password matches the current password.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted."
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
async def change_account_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    """Change password with current-password verification."""
    user = await account_settings_service.change_password(db, current_user, body)
    return ChangePasswordResponse(
        message="Password changed successfully",
        description="Your new password is now active",
        id=user.id,
        phone=body.phone,
    )


@router.put(
    "/organization",
    response_model=OrganizationSettingsResponse,
    operation_id="updateAccountOrganization",
    summary="Update organization information",
    description=(
        "Update the authenticated user's organization name.\n\n"
        "Requires **Bearer JWT**. Returns **200** on success.\n\n"
        "Returns **400** when the user has no linked organization or the name is empty.\n\n"
        "Returns **409** when another organization already uses the requested name.\n\n"
        "Optional `phone` is client metadata and is not persisted."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_account_organization(
    body: OrganizationSettingsRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationSettingsResponse:
    """Update organization settings for the authenticated user."""
    organization = await account_settings_service.update_organization_settings(
        db,
        current_user,
        body,
    )
    return OrganizationSettingsResponse(
        message="Organization updated successfully",
        description="Your organization details have been saved",
        id=current_user.id,
        organization_name=organization.name,
    )


@router.put(
    "/authentication-keys",
    response_model=AuthKeysResponse,
    operation_id="updateAuthenticationKeys",
    summary="Update authentication keys",
    description=(
        "Store authentication keys for third-party integrations on the user account.\n\n"
        "Requires **Bearer JWT**. Keys are persisted in user metadata.\n\n"
        "Returns **400** when either key is empty."
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
async def update_authentication_keys(
    body: AuthKeysRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> AuthKeysResponse:
    """Update stored authentication keys."""
    user = await account_settings_service.update_authentication_keys(db, current_user, body)
    keys = account_settings_service.get_auth_keys(user)
    return AuthKeysResponse(
        message="Authentication keys updated successfully",
        description="Your authentication keys have been saved",
        id=user.id,
        auth_keys=keys,
    )


@router.patch(
    "/push-notifications",
    response_model=PushNotificationsResponse,
    operation_id="updatePushNotifications",
    summary="Enable or disable push notifications",
    description=(
        "Update push notification preference for the authenticated user.\n\n"
        "Requires **Bearer JWT**. Only **org_admin** users (or super admins) may enable "
        "push notifications.\n\n"
        "Returns **400** when a non-authorized user attempts to enable notifications.\n\n"
        "Optional `phone` is client metadata and is not persisted."
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
async def update_push_notifications(
    body: PushNotificationsRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PushNotificationsResponse:
    """Update push notification settings."""
    user = await account_settings_service.update_push_notifications(db, current_user, body)
    enabled = account_settings_service.get_push_notifications_enabled(user)
    description = (
        "Push notifications are now enabled"
        if enabled
        else "Push notifications are now disabled"
    )
    return PushNotificationsResponse(
        message="Push notification preference updated",
        description=description,
        id=user.id,
        push_notifications_enabled=enabled,
    )


@router.get(
    "/help-support",
    response_model=HelpSupportResponse,
    operation_id="getHelpSupport",
    summary="Retrieve help and support information",
    description=(
        "Return help articles, support contact details, and profile header summary "
        "for the Account Settings help screen.\n\n"
        "Requires **Bearer JWT**. Returns **200** with articles even when the list is empty."
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
async def get_help_support(
    current_user: User = Depends(require_authenticated_user),
) -> HelpSupportResponse:
    """Load help articles and support resources."""
    payload = account_settings_service.build_help_support_payload(current_user)
    return HelpSupportResponse(**payload)


@router.put(
    "/profile",
    response_model=AccountProfileUpdateResponse,
    operation_id="updateAccountSettingsProfile",
    summary="Update account profile details",
    description=(
        "Update the authenticated user's profile from Account Settings using `full_name` "
        "and `email`.\n\n"
        "Requires **Bearer JWT**. Returns **200** on success.\n\n"
        "Returns **400** when required fields are missing or invalid.\n\n"
        "Returns **409** when the email is already used by another account.\n\n"
        "Optional `phone` is client metadata and is not persisted."
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
async def update_account_settings_profile(
    body: AccountProfileUpdateRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> AccountProfileUpdateResponse:
    """Update profile details for the Account Settings screen."""
    updated_user = await account_settings_service.update_account_profile(
        db,
        current_user,
        body,
    )
    result = profile_service.build_coach_profile_response(
        updated_user,
        message="Profile updated successfully",
        description="Your profile changes have been saved",
        status="saved",
    )
    result["title"] = "Account Settings"
    return AccountProfileUpdateResponse(**result)


@router.post(
    "/help-support/contact",
    response_model=SupportSubmitResponse,
    operation_id="submitAccountSettingsSupport",
    summary="Submit a support request from Account Settings",
    description=(
        "Submit a support inquiry from the Account Settings help screen.\n\n"
        "Requires **Bearer JWT**. Returns **200** on success.\n\n"
        "Returns **400** for missing fields, invalid email, non-numeric phone, or "
        "messages longer than 500 characters.\n\n"
        "Returns **409** when `inquiry_subject` is not one of the predefined options."
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
async def submit_account_settings_support(
    body: SupportSubmitRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SupportSubmitResponse:
    """Submit a support message from Account Settings."""
    support_request = await account_settings_service.submit_support_request(
        db,
        current_user,
        body,
    )
    return SupportSubmitResponse(
        message="Your support request has been submitted successfully",
        description="Our support team typically responds within 24 hours",
        id=current_user.id,
        request_id=support_request.id,
    )
