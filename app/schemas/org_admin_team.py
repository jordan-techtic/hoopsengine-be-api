"""Pydantic schemas for organization admin team CRUD APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

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
    "message": "Team loaded successfully",
    "status": "active",
    "description": "Premier elite development squad preparing for state level championship.",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Varsity Squad",
    "full_name": "Varsity Squad",
    "code": "VB-2026",
    "organization": "Courtside Elite Academy",
    "team_name": "Varsity Squad",
    "team_code": "VB-2026",
    "team_description": "Premier elite development squad preparing for state level championship.",
    "age_group": "16-18",
    "coaches": [
        {
            "id": "22222222-3333-4444-5555-666666666666",
            "coach_id": "22222222-3333-4444-5555-666666666666",
            "name": "Coach Dave Miller",
        }
    ],
}

ORG_ADMIN_TEAM_EDIT_UPDATE_EXAMPLE = {
    "full_name": "Varsity Squad",
    "description": "Premier elite development squad preparing for state level championship.",
    "coaches": [
        {
            "coach_id": "22222222-3333-4444-5555-666666666666",
            "name": "Coach Dave Miller",
        }
    ],
    "phone": "+1-555-0100",
}


class OrgAdminTeamCoachInput(BaseModel):
    """Coach assignment entry within an org-admin team write request."""

    id: UUID | None = Field(
        default=None,
        description="Coach UUID from the organization roster",
        examples=["22222222-3333-4444-5555-666666666666"],
    )
    coach_id: UUID | None = Field(
        default=None,
        description="Edit Team Figma alias for coach UUID",
        examples=["22222222-3333-4444-5555-666666666666"],
    )
    name: str = Field(
        description="Coach display name shown in the team form",
        examples=["Coach Dave Miller"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Normalize coach display name text."""
        return value.strip()

    @model_validator(mode="after")
    def resolve_coach_id(self) -> Self:
        """Accept either `id` or `coach_id` from Create/Edit Team payloads."""
        resolved = self.id or self.coach_id
        if resolved is None:
            raise ValueError("Coach id is required")
        object.__setattr__(self, "id", resolved)
        return self


class OrgAdminTeamCoachItem(BaseModel):
    """Coach assignment returned with an org-admin team."""

    id: UUID = Field(description="Coach UUID")
    name: str = Field(description="Coach display name", examples=["Coach Dave Miller"])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coach_id(self) -> UUID:
        """Edit Team Figma alias mirroring `id`."""
        return self.id


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

    @model_validator(mode="after")
    def map_figma_create_fields(self) -> Self:
        """Map Create Team Figma aliases onto persisted team fields."""
        if self.full_name is not None and not self.team_name.strip():
            object.__setattr__(self, "team_name", self.full_name.strip())
        return self


class OrgAdminTeamUpdateRequest(BaseModel):
    """Payload for PUT /admin/teams/{team_id} (Edit Team screen)."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_TEAM_EDIT_UPDATE_EXAMPLE}
    )

    team_name: str | None = Field(
        default=None,
        description="Updated team display name",
    )
    name: str | None = Field(
        default=None,
        description="Alias for team display name from legacy ticket examples",
        examples=["Varsity Squad"],
    )
    team_code: str | None = Field(
        default=None,
        description="Updated unique team code",
    )
    team_description: str | None = Field(
        default=None,
        description="Updated team description",
    )
    description: str | None = Field(
        default=None,
        description="Figma Description field; maps to team_description when provided",
        examples=["Premier elite development squad preparing for state level championship."],
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
        description="Figma Team Name field; maps to team_name when provided",
        examples=["Varsity Squad"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("team_name", "team_code", "name", "full_name", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def map_figma_edit_fields(self) -> Self:
        """Map Edit Team Figma aliases onto persisted team fields."""
        if self.full_name is not None and self.team_name is None:
            object.__setattr__(self, "team_name", self.full_name.strip())
        elif self.name is not None and self.team_name is None:
            object.__setattr__(self, "team_name", self.name.strip())
        if self.description is not None and self.team_description is None:
            object.__setattr__(self, "team_description", self.description)
        return self


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
    full_name: str = Field(description="Figma Team Name field (`full_name`)")
    code: str = Field(description="Unique team code")
    organization: str = Field(description="Organization display name")
    team_name: str
    team_code: str
    team_description: str | None = None
    age_group: str | None = None
    coaches: list[OrgAdminTeamCoachItem] = Field(default_factory=list)
    created_at: datetime | None = None
