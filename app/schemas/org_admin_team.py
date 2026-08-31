"""Pydantic schemas for organization admin team CRUD APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

ORG_ADMIN_TEAM_CREATE_EXAMPLE = {
    "team_name": "Varsity Boys",
    "team_code": "VB-2026",
    "team_description": "Competitive varsity roster for the 2026 season",
    "age_group": "16-18",
    "coaches": [
        {
            "id": "22222222-3333-4444-5555-666666666666",
            "name": "Coach Taylor",
        }
    ],
    "full_name": "Varsity Boys",
    "phone": "+1-555-0100",
}

ORG_ADMIN_TEAM_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Team created successfully",
    "status": "active",
    "description": "Competitive varsity roster for the 2026 season",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Varsity Boys",
    "code": "VB-2026",
    "organization": "Courtside Elite Academy",
    "team_name": "Varsity Boys",
    "team_code": "VB-2026",
    "team_description": "Competitive varsity roster for the 2026 season",
    "age_group": "16-18",
    "coaches": [
        {
            "id": "22222222-3333-4444-5555-666666666666",
            "name": "Coach Taylor",
        }
    ],
}


class OrgAdminTeamCoachInput(BaseModel):
    """Coach assignment entry within an org-admin team write request."""

    id: UUID = Field(
        description="Coach UUID from the organization roster",
        examples=["22222222-3333-4444-5555-666666666666"],
    )
    name: str = Field(
        description="Coach display name shown in the Create Team form",
        examples=["Coach Taylor"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Normalize coach display name text."""
        return value.strip()


class OrgAdminTeamCoachItem(BaseModel):
    """Coach assignment returned with an org-admin team."""

    id: UUID = Field(description="Coach UUID")
    name: str = Field(description="Coach display name", examples=["Coach Taylor"])


class OrgAdminTeamCreateRequest(BaseModel):
    """Payload for POST /admin/teams."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_TEAM_CREATE_EXAMPLE})

    team_name: str = Field(
        description="Team display name",
        examples=["Varsity Boys"],
    )
    team_code: str = Field(
        description="Unique team code used for roster lookup",
        examples=["VB-2026"],
    )
    team_description: str | None = Field(
        default=None,
        description="Optional team description",
        examples=["Competitive varsity roster for the 2026 season"],
    )
    age_group: str | None = Field(
        default=None,
        description="Age group label selected in the Create Team dropdown",
        examples=["16-18"],
    )
    coaches: list[OrgAdminTeamCoachInput] = Field(
        default_factory=list,
        description="Coaches assigned to the team",
    )
    full_name: str | None = Field(
        default=None,
        description="Optional client metadata from the team name field (not persisted)",
        examples=["Varsity Boys"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("team_name", "team_code")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Normalize required text fields."""
        return value.strip()


class OrgAdminTeamUpdateRequest(BaseModel):
    """Payload for PUT /admin/teams/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "team_name": "Updated Varsity Boys",
                "team_code": "VB-2026-A",
                "team_description": "Updated roster description",
                "age_group": "17-18",
                "coaches": [
                    {
                        "id": "22222222-3333-4444-5555-666666666666",
                        "name": "Coach Taylor",
                    }
                ],
                "phone": "+1-555-0100",
            }
        }
    )

    team_name: str | None = Field(
        default=None,
        description="Updated team display name",
    )
    team_code: str | None = Field(
        default=None,
        description="Updated unique team code",
    )
    team_description: str | None = Field(
        default=None,
        description="Updated team description",
    )
    age_group: str | None = Field(
        default=None,
        description="Updated age group label",
    )
    coaches: list[OrgAdminTeamCoachInput] | None = Field(
        default=None,
        description="Replacement coach assignment list",
    )
    full_name: str | None = Field(
        default=None,
        description="Optional client metadata from the team name field (not persisted)",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )

    @field_validator("team_name", "team_code")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""
        if value is None:
            return None
        return value.strip()


class OrgAdminTeamResponse(MobileWriteOnlyPasswordMixin):
    """Single org-admin team mutation or detail response."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_TEAM_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="active", description="Team lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    name: str = Field(description="Team display name")
    code: str = Field(description="Unique team code")
    organization: str = Field(description="Organization display name")
    team_name: str
    team_code: str
    team_description: str | None = None
    age_group: str | None = None
    coaches: list[OrgAdminTeamCoachItem] = Field(default_factory=list)
    created_at: datetime | None = None
