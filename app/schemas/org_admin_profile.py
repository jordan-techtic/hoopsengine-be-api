"""Pydantic schemas for organization admin profile API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.profile import ProfileImageResponse

ORG_PROFILE_UPDATE_EXAMPLE = {
    "organization_name": "Courtside Elite Academy",
    "address": "1234 Basketball Ave",
    "email": "alex.morgan@academy.com",
    "phone_number": "+1 (555) 382-9102",
    "first_name": "Jane",
    "last_name": "Doe",
    "phone": "+1-555-0100",
}

ORG_PROFILE_MANAGEMENT_UPDATE_EXAMPLE = {
    "name": "Courtside Elite Academy",
    "description": "Premier youth basketball development organization",
    "contact_info": "contact@courtside.com",
}

ORG_PROFILE_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Organization profile loaded successfully",
    "status": "ready",
    "description": "Review and update your organization details",
    "link": None,
    "error": None,
    "title": "Edit Organization Profile",
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Courtside Elite Academy",
    "organization": "Courtside Elite Academy",
    "organization_name": "Courtside Elite Academy",
    "address": "1234 Basketball Ave",
    "email": "alex.morgan@academy.com",
    "phone_number": "+1 (555) 382-9102",
    "phone": "+1 (555) 382-9102",
    "first_name": "Jane",
    "last_name": "Doe",
    "organization_description": "Premier youth basketball development organization",
    "contact_info": "contact@courtside.com",
    "avatar": None,
    "profile": {
        "organization_name": "Courtside Elite Academy",
        "address": "1234 Basketball Ave",
        "email": "alex.morgan@academy.com",
        "phone_number": "+1 (555) 382-9102",
        "first_name": "Jane",
        "last_name": "Doe",
        "organization_description": "Premier youth basketball development organization",
        "contact_info": "contact@courtside.com",
    },
}


class OrganizationProfileNested(BaseModel):
    """Nested profile object for the Edit Organization Profile screen."""

    organization_name: str = Field(description="Organization display name")
    address: str | None = Field(default=None, description="Organization street address")
    email: EmailStr = Field(description="Organization contact email")
    phone_number: str | None = Field(default=None, description="Organization phone number")
    first_name: str | None = Field(default=None, description="Organization admin first name")
    last_name: str | None = Field(default=None, description="Organization admin last name")
    organization_description: str | None = Field(
        default=None,
        description="Organization description text",
    )
    contact_info: str | None = Field(
        default=None,
        description="Organization contact information (email or phone)",
    )


class OrganizationProfileUpdateRequest(BaseModel):
    """Payload for PUT /organization/profile."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_PROFILE_UPDATE_EXAMPLE})

    organization_name: str | None = Field(
        default=None,
        description="Organization display name (Edit Organization Profile form)",
        examples=["Courtside Elite Academy"],
    )
    address: str | None = Field(
        default=None,
        description="Organization street address",
        examples=["1234 Basketball Ave"],
    )
    email: str | None = Field(
        default=None,
        description="Organization contact email address",
        examples=["alex.morgan@academy.com"],
    )
    phone_number: str | None = Field(
        default=None,
        description="Organization contact phone number",
        examples=["+1 (555) 382-9102"],
    )
    first_name: str | None = Field(
        default=None,
        description="Organization admin first name (InputGroup-First Name)",
        examples=["Jane"],
    )
    last_name: str | None = Field(
        default=None,
        description="Organization admin last name (InputGroup-Last Name)",
        examples=["Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    name: str | None = Field(
        default=None,
        description="Organization display name (Organization Profile Management form)",
        examples=["Courtside Elite Academy"],
    )
    description: str | None = Field(
        default=None,
        description="Organization description text",
        examples=["Premier youth basketball development organization"],
    )
    contact_info: str | None = Field(
        default=None,
        description="Organization contact information — valid email or phone number",
        examples=["contact@courtside.com"],
    )


class OrganizationProfileResponse(MobileWriteOnlyPasswordMixin):
    """GET/PUT organization profile response for the org admin Edit Profile screen."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_PROFILE_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable outcome message")
    status: str = Field(default="ready", description="UI state indicator")
    description: str | None = Field(default=None, description="Secondary UI message")
    link: str | None = Field(default=None, description="Optional related link")
    error: None = Field(default=None)
    title: str = Field(default="Edit Organization Profile")
    id: UUID = Field(description="Organization UUID")
    name: str = Field(description="Organization display name")
    organization: str = Field(description="Organization name alias for frontend binding")
    organization_name: str = Field(description="Organization display name")
    address: str | None = Field(default=None, description="Organization street address")
    email: EmailStr = Field(description="Organization contact email")
    phone_number: str | None = Field(default=None, description="Organization phone number")
    phone: str | None = Field(
        default=None,
        description="Organization phone alias (same as phone_number on read)",
    )
    first_name: str | None = Field(default=None, description="Organization admin first name")
    last_name: str | None = Field(default=None, description="Organization admin last name")
    organization_description: str | None = Field(
        default=None,
        description="Organization description text",
    )
    contact_info: str | None = Field(
        default=None,
        description="Organization contact information (email or phone)",
    )
    avatar: ProfileImageResponse | None = Field(
        default=None,
        description="Organization logo or admin avatar when available",
    )
    profile: OrganizationProfileNested = Field(description="Nested profile for form binding")
