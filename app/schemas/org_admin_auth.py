"""Pydantic schemas for Organization Admin authentication (HE-423)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

ORG_ADMIN_LOGIN_REQUEST_EXAMPLE = {
    "email": "orgadmin@test.com",
    "username": "orgadmin@test.com",
    "password": "OrgAdmin123!",
    "phone": "+1-555-0100",
    "remember_me": False,
}


class OrgAdminUserPublic(BaseModel):
    """Organization admin profile fields returned after login."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str | None = None
    role: UserRole
    org_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_super_admin: bool
    is_active: bool
    last_sign_in_at: datetime | None = None


class OrgAdminLoginRequest(BaseModel):
    """Payload for POST /organization/login."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_LOGIN_REQUEST_EXAMPLE})

    email: str | None = Field(
        default=None,
        description="Organization admin email address (maps ticket username/email)",
        examples=["orgadmin@test.com"],
    )
    username: str | None = Field(
        default=None,
        description="Alternative login identifier when email is omitted",
        examples=["orgadmin@test.com"],
    )
    password: str = Field(
        ...,
        description="Account password (required)",
        examples=["OrgAdmin123!"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    remember_me: bool = Field(
        default=False,
        description="When true, issue a longer-lived JWT for extended sessions",
        examples=[False],
    )


class OrgAdminLoginResponse(MobileWriteOnlyPasswordMixin):
    """Successful organization admin login response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "title": "LOGIN",
                "message": "Login successful! Redirecting to dashboard...",
                "status": "authenticated",
                "description": "Welcome back to Hoops Engine",
                "link": "http://localhost:5173/organization/dashboard",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "email": "orgadmin@test.com",
                "username": "orgadmin",
                "organization": "Courtside Elite Academy",
                "password": None,
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "remember_me": False,
                "user": {
                    "id": "11111111-2222-3333-4444-555555555555",
                    "email": "orgadmin@test.com",
                    "username": "orgadmin",
                    "role": "org_admin",
                    "org_id": "00000000-0000-4000-8000-000000000010",
                    "is_super_admin": False,
                    "is_active": True,
                },
            }
        }
    )

    success: bool = Field(default=True, description="Always true on successful login")
    title: str = Field(default="LOGIN", description="Screen title for the login UI")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="authenticated", description="Login status after success")
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown after login",
    )
    link: str | None = Field(
        default=None,
        description="Dashboard navigation target after successful login",
    )
    error: None = Field(default=None, description="Always null on success")
    id: UUID = Field(description="Authenticated organization admin user id")
    email: EmailStr = Field(description="Authenticated user email")
    username: str | None = Field(default=None, description="Authenticated username when set")
    organization: str | None = Field(
        default=None,
        description="Organization name linked to the admin account",
    )
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type for Authorization header")
    expires_in_hours: int = Field(description="JWT validity in hours")
    remember_me: bool = Field(description="Whether an extended session token was issued")
    user: OrgAdminUserPublic = Field(description="Authenticated organization admin profile")
