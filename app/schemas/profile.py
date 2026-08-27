from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class ProfileImageResponse(BaseModel):
    url: str | None = None
    original_name: str | None = None
    content_type: str | None = None


class SuperAdminProfileResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "a752feb1-7852-4a3e-9d07-2628b9873cb1",
                "name": "Super Admin",
                "email": "admin.hoopsengine@yopmail.com",
                "profile_image": {
                    "url": "/api/v1/super-admin/profile/avatar",
                    "original_name": "avatar.png",
                    "content_type": "image/png",
                },
                "updated_at": "2026-08-19T10:00:00.000000Z",
            }
        }
    )

    id: UUID
    name: str
    email: EmailStr
    profile_image: ProfileImageResponse | None = None
    updated_at: datetime


class SuperAdminProfileUpdateResponse(BaseModel):
    message: str
    profile: SuperAdminProfileResponse


COACH_PROFILE_UPDATE_EXAMPLE = {
    "first_name": "Lebron",
    "last_name": "James",
    "phone_number": "+1 (555) 382-9102",
    "date_of_birth": "08/24/1992",
    "gender": "Male",
    "grade": "Academy Head",
    "username": "alex_morgan",
    "email": "alex.morgan@academy.com",
    "parent_guardian": "Not Applicable",
    "phone": "+1-555-0100",
}


class CoachProfileUpdateRequest(BaseModel):
    """Payload for PUT /profile."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_PROFILE_UPDATE_EXAMPLE})

    first_name: str = Field(description="First name (required)", examples=["Lebron"])
    last_name: str = Field(description="Last name (required)", examples=["James"])
    email: str = Field(description="Email address (required)", examples=["alex.morgan@academy.com"])
    username: str | None = Field(
        default=None,
        description="Unique username",
        examples=["alex_morgan"],
    )
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number",
        examples=["+1 (555) 382-9102"],
    )
    date_of_birth: str | None = Field(
        default=None,
        description="Date of birth in MM/DD/YYYY format",
        examples=["08/24/1992"],
    )
    gender: str | None = Field(default=None, description="Gender", examples=["Male"])
    grade: str | None = Field(default=None, description="Grade or role label", examples=["Academy Head"])
    parent_guardian: str | None = Field(
        default=None,
        description="Parent or guardian name",
        examples=["Not Applicable"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachProfileData(BaseModel):
    """Nested editable profile fields for the mobile client."""

    first_name: str | None = Field(default=None, description="First name", examples=["Lebron"])
    last_name: str | None = Field(default=None, description="Last name", examples=["James"])
    email: EmailStr = Field(description="Email address", examples=["alex.morgan@academy.com"])
    username: str | None = Field(default=None, description="Unique username", examples=["alex_morgan"])
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number",
        examples=["+1 (555) 382-9102"],
    )
    date_of_birth: str | None = Field(
        default=None,
        description="Date of birth in MM/DD/YYYY format",
        examples=["08/24/1992"],
    )
    gender: str | None = Field(default=None, description="Gender", examples=["Male"])
    grade: str | None = Field(default=None, description="Grade or role label", examples=["Academy Head"])
    parent_guardian: str | None = Field(
        default=None,
        description="Parent or guardian name",
        examples=["Not Applicable"],
    )


class CoachProfileResponse(MobileWriteOnlyPasswordMixin):
    """Coach edit profile response envelope."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Profile loaded successfully",
                "status": "ready",
                "description": "Review and update your personal information",
                "link": None,
                "error": None,
                "title": "Edit Profile",
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "Lebron James",
                "first_name": "Lebron",
                "last_name": "James",
                "email": "alex.morgan@academy.com",
                "username": "alex_morgan",
                "phone_number": "+1 (555) 382-9102",
                "phone": "+1 (555) 382-9102",
                "date_of_birth": "08/24/1992",
                "gender": "Male",
                "grade": "Academy Head",
                "parent_guardian": "Not Applicable",
                "address": None,
                "avatar": None,
                "profile": {
                    "first_name": "Lebron",
                    "last_name": "James",
                    "email": "alex.morgan@academy.com",
                    "username": "alex_morgan",
                    "phone_number": "+1 (555) 382-9102",
                    "date_of_birth": "08/24/1992",
                    "gender": "Male",
                    "grade": "Academy Head",
                    "parent_guardian": "Not Applicable",
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
    title: str = Field(default="Edit Profile")
    id: UUID
    name: str
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr
    username: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    grade: str | None = None
    parent_guardian: str | None = None
    address: str | None = None
    avatar: ProfileImageResponse | None = None
    profile: CoachProfileData
