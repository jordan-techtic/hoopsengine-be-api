"""Pydantic schemas for Player Edit Profile API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.profile import ProfileImageResponse

PLAYER_PROFILE_UPDATE_EXAMPLE = {
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


class PlayerProfileUpdateRequest(BaseModel):
    """Payload for PUT /player/profile."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_PROFILE_UPDATE_EXAMPLE})

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
        description="Contact phone number in +1 (555) 382-9102 format",
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


class PlayerProfileData(BaseModel):
    """Nested editable profile fields for the Player Edit Profile screen."""

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


class PlayerProfileResponse(MobileWriteOnlyPasswordMixin):
    """Player edit profile response envelope."""

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
                "id": "00000000-0000-4000-8000-000000000003",
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
                "password": None,
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

    success: bool = Field(default=True, description="Always true on successful profile load or update")
    message: str = Field(description="Human-readable status message for the Edit Profile screen")
    status: str = Field(default="ready", description="Profile state (ready, saved, etc.)")
    description: str | None = Field(default=None, description="Optional subtitle or helper text")
    link: str | None = Field(default=None, description="Optional navigation link")
    error: None = Field(default=None, description="Always null on success")
    title: str = Field(default="Edit Profile", description="Screen title shown in the mobile header")
    id: UUID = Field(description="Authenticated player user identifier")
    name: str = Field(description="Display name (typically first_name + last_name)")
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
    profile: PlayerProfileData
