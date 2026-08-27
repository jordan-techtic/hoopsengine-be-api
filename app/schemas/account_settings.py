"""Pydantic schemas for Account Settings APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.profile import CoachProfileResponse

CHANGE_PASSWORD_EXAMPLE = {
    "current_password": "StrongPassword123!",
    "new_password": "NewSecure456!",
    "phone": "+1-555-0100",
}

ORGANIZATION_SETTINGS_EXAMPLE = {
    "organization_name": "Hoops Academy",
    "phone": "+1-555-0100",
}

AUTH_KEYS_EXAMPLE = {
    "auth_keys": {
        "key1": "integration-key-alpha",
        "key2": "integration-key-beta",
    },
    "phone": "+1-555-0100",
}

PUSH_NOTIFICATIONS_EXAMPLE = {
    "push_notifications_enabled": True,
    "phone": "+1-555-0100",
}

PROFILE_UPDATE_EXAMPLE = {
    "full_name": "Jane Doe",
    "email": "jane.doe@academy.com",
    "phone": "+1-555-0100",
}

SUPPORT_SUBMIT_EXAMPLE = {
    "email": "user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "I need help resetting my password.",
}


class ChangePasswordRequest(BaseModel):
    """Payload for POST /account/settings/change-password."""

    model_config = ConfigDict(json_schema_extra={"example": CHANGE_PASSWORD_EXAMPLE})

    current_password: str = Field(
        ...,
        description="Current account password for verification",
        examples=["StrongPassword123!"],
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="New password meeting strength requirements",
        examples=["NewSecure456!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class ChangePasswordResponse(MobileWriteOnlyPasswordMixin):
    """Successful password change response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Password changed successfully",
                "status": "password_changed",
                "description": "Your new password is now active",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "password": None,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="password_changed")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    phone: str | None = None


class OrganizationSettingsRequest(BaseModel):
    """Payload for PUT /account/settings/organization."""

    model_config = ConfigDict(json_schema_extra={"example": ORGANIZATION_SETTINGS_EXAMPLE})

    organization_name: str = Field(
        ...,
        min_length=1,
        description="Updated organization display name",
        examples=["Hoops Academy"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class OrganizationSettingsResponse(MobileWriteOnlyPasswordMixin):
    """Organization settings update response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Organization updated successfully",
                "status": "saved",
                "description": "Your organization details have been saved",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "organization_name": "Hoops Academy",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="saved")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    organization_name: str


class AuthKeysPayload(BaseModel):
    """Nested authentication keys object."""

    key1: str = Field(..., min_length=1, description="Primary authentication key")
    key2: str = Field(..., min_length=1, description="Secondary authentication key")


class AuthKeysRequest(BaseModel):
    """Payload for PUT /account/settings/authentication-keys."""

    model_config = ConfigDict(json_schema_extra={"example": AUTH_KEYS_EXAMPLE})

    auth_keys: AuthKeysPayload = Field(description="Authentication key pair for integrations")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class AuthKeysResponse(MobileWriteOnlyPasswordMixin):
    """Authentication keys update response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Authentication keys updated successfully",
                "status": "saved",
                "description": "Your authentication keys have been saved",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "auth_keys": {"key1": "integration-key-alpha", "key2": "integration-key-beta"},
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="saved")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    auth_keys: dict[str, str]


class PushNotificationsRequest(BaseModel):
    """Payload for PATCH /account/settings/push-notifications."""

    model_config = ConfigDict(json_schema_extra={"example": PUSH_NOTIFICATIONS_EXAMPLE})

    push_notifications_enabled: bool = Field(
        description="Whether push notifications are enabled for this account",
        examples=[True],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PushNotificationsResponse(MobileWriteOnlyPasswordMixin):
    """Push notification preference response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Push notification preference updated",
                "status": "saved",
                "description": "Push notifications are now enabled",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "push_notifications_enabled": True,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="saved")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    push_notifications_enabled: bool


class HelpArticleItem(BaseModel):
    """One help article shown on the Account Settings help screen."""

    question: str = Field(description="Help article title or question")
    answer: str = Field(description="Help article body or answer")


class HelpSupportContactInfo(BaseModel):
    """Support contact details."""

    email: str = Field(description="Support team email address")
    phone: str = Field(description="Support team phone number")


class AccountSettingsProfileSummary(BaseModel):
    """Profile header summary for the Account Settings screen."""

    id: UUID
    name: str = Field(description="Display name for the profile header")
    full_name: str = Field(description="Full name shown in the profile header")
    role: str = Field(description="User role label for the profile header")
    profile: dict[str, str | None] = Field(description="Nested profile fields for the client")


class HelpSupportResponse(MobileWriteOnlyPasswordMixin):
    """GET /account/settings/help-support response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Help and support loaded successfully",
                "status": "ready",
                "description": "Review help articles and contact support",
                "link": "/api/v1/account/settings/help-support/contact",
                "error": None,
                "title": "Help & Support",
                "articles": [
                    {
                        "question": "How do I change my password?",
                        "answer": "Go to Account Settings and select Change Password.",
                    }
                ],
                "contact": {"email": "support@hoopsengine.com", "phone": "+15558392001"},
                "profile": {
                    "id": "11111111-2222-3333-4444-555555555555",
                    "name": "Jane Doe",
                    "full_name": "Jane Doe",
                    "role": "coach",
                    "profile": {"email": "jane@example.com"},
                },
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    title: str = Field(default="Help & Support")
    articles: list[HelpArticleItem]
    contact: HelpSupportContactInfo
    profile: AccountSettingsProfileSummary


class AccountProfileUpdateRequest(BaseModel):
    """Payload for PUT /account/settings/profile."""

    model_config = ConfigDict(json_schema_extra={"example": PROFILE_UPDATE_EXAMPLE})

    full_name: str = Field(
        ...,
        min_length=1,
        description="Full display name (user-name from Figma)",
        examples=["Jane Doe"],
    )
    email: EmailStr = Field(description="Email address", examples=["jane.doe@academy.com"])
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class SupportSubmitRequest(BaseModel):
    """Payload for POST /account/settings/help-support/contact."""

    model_config = ConfigDict(json_schema_extra={"example": SUPPORT_SUBMIT_EXAMPLE})

    email: str = Field(description="Contact email address", examples=["user@example.com"])
    phone: str = Field(..., min_length=1, description="Contact phone number (numeric digits)")
    inquiry_subject: str = Field(..., min_length=1, description="Selected inquiry subject")
    message_description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Support message body (max 500 characters)",
    )


class SupportSubmitResponse(MobileWriteOnlyPasswordMixin):
    """Successful support submission from Account Settings."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Your support request has been submitted successfully",
                "status": "submitted",
                "description": "Our support team typically responds within 24 hours",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "request_id": "22222222-3333-4444-5555-666666666666",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="submitted")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    request_id: UUID


class AccountProfileUpdateResponse(CoachProfileResponse):
    """Profile update response reusing the coach profile envelope."""

    title: str = Field(default="Account Settings")
