"""Pydantic schemas for organization admin coach management APIs."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

COACH_REMOVAL_CONFIRMATION_MESSAGE = (
    "Are you sure you want to remove this coach from your organization? "
    "This action is permanent."
)

ORG_ADMIN_COACH_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Coach details loaded successfully",
    "status": "ready",
    "description": "Coach profile and contact information",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Sarah Jenkins",
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "+1 (555) 123-4567",
    "phone_number": "+1 (555) 123-4567",
    "team_assignment": "Varsity Squad",
    "team": "Varsity Squad",
    "coach_id": "11111111-2222-3333-4444-555555555555",
    "confirmation_message": COACH_REMOVAL_CONFIRMATION_MESSAGE,
    "organization": "Seeded Hoops Club",
}

ORG_ADMIN_COACH_REMOVAL_REQUEST_EXAMPLE = {
    "phone": "+1-555-0100",
}


class OrgAdminCoachUpdateRequest(BaseModel):
    """Payload for PUT /admin/coaches/{coach_id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Doe",
                "email": "sarah.jenkins@school.edu",
                "phone": "+1 (555) 123-4567",
                "team_assignment": "Varsity Squad",
            }
        }
    )

    full_name: str = Field(
        description="Figma Name field; split into first_name and last_name when saved",
        examples=["Jane Doe"],
    )
    name: str | None = Field(
        default=None,
        description="Alias for full_name from legacy ticket examples",
        examples=["Sarah Jenkins"],
    )
    email: str = Field(
        description="Coach contact email (must be unique across the system)",
        examples=["sarah.jenkins@school.edu"],
    )
    phone: str = Field(
        description=(
            "Figma Phone field; persisted on the linked coach user account when one "
            "exists for the coach email"
        ),
        examples=["+1 (555) 123-4567"],
    )
    team_assignment: str | None = Field(
        default=None,
        description="Team display name to assign within the organization",
        examples=["Varsity Squad"],
    )

    @model_validator(mode="after")
    def map_figma_aliases(self) -> Self:
        """Apply Figma alias fields before service validation."""
        display_name = (self.full_name or self.name or "").strip()
        if display_name and display_name != self.full_name:
            object.__setattr__(self, "full_name", display_name)
        return self


class OrgAdminCoachDetailResponse(BaseModel):
    """Coach detail response for the Organization Admin Edit Coach screen."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_COACH_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Coach UUID from the client-domain coaches table")
    name: str = Field(description="Coach full display name")
    full_name: str = Field(description="Figma Name field (`full_name`)")
    email: str | None = Field(default=None, description="Coach contact email")
    phone_number: str | None = Field(
        default=None,
        description="Stored contact phone from the linked coach user account",
    )
    phone: str | None = Field(
        default=None,
        description="Echo of stored phone for Figma Phone field display",
    )
    team_assignment: str | None = Field(
        default=None,
        description="Figma Team Assignment field (team display name)",
    )
    organization: str = Field(description="Organization display name")
    team: str | None = Field(
        default=None,
        description="Team display name for the Remove Coach screen (same as team_assignment)",
    )
    coach_id: UUID | None = Field(
        default=None,
        description="Same as id — bound for mobile Remove Coach detail screens",
    )
    confirmation_message: str | None = Field(
        default=None,
        description="Exact confirmation modal copy shown before coach removal",
    )


class OrgAdminCoachRemovalRequest(BaseModel):
    """Optional payload for DELETE /admin/coaches/{coach_id}."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_COACH_REMOVAL_REQUEST_EXAMPLE}
    )

    phone: str | None = Field(
        default=None,
        description=(
            "Figma Phone metadata from the Remove Coach screen status bar; "
            "validated when provided but not required for removal"
        ),
        examples=["+1-555-0100"],
    )
