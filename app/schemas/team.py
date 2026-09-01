"""Pydantic schemas for Team Details APIs (/api/v1/teams)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.pagination import PaginationMeta

TEAM_LISTING_CREATE_EXAMPLE = {
    "name": "Varsity Squad",
    "age_group": "U16",
    "coaches": [{"name": "John Doe"}],
    "players": [{"name": "Player One"}, {"name": "Player Two"}],
    "phone": "+1-555-0100",
}

TEAM_DETAILS_UPDATE_EXAMPLE = {
    "name": "Varsity Squad",
    "email": "coach.taylor@school.edu",
    "season": "2025-2026",
    "home_ground": "West Campus Court",
    "age_group": "16-18",
    "training_schedule": "Tue/Thu 5:00 PM",
    "phone": "+1-555-0100",
    "role": "head_coach",
    "coaches": ["Coach Taylor", "Coach James"],
    "players": ["Sarah Jenkins"],
}

TEAM_DETAILS_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Team details loaded successfully",
    "status": "active",
    "description": "Varsity roster and coaching staff",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Varsity Boys",
    "season": "2025-2026",
    "home_ground": "Main Gymnasium",
    "coaches": ["Coach Taylor"],
    "players": ["Sarah Jenkins"],
    "founded": "2018-09-01",
    "age_group": "16-18",
    "training_schedule": "Mon/Wed 4:00 PM",
    "phone": "+1-555-0100",
    "phone_number": "+1-555-0100",
    "email": "coach.taylor@school.edu",
    "role": "head_coach",
    "roles": ["head_coach"],
    "organization": "Seeded Hoops Club",
}

TEAM_DETAILS_CREATE_EXAMPLE = {
    "name": "Varsity Boys",
    "email": "coach.taylor@school.edu",
    "season": "2025-2026",
    "home_ground": "Main Gymnasium",
    "age_group": "16-18",
    "training_schedule": "Mon/Wed 4:00 PM",
    "founded": "2018-09-01",
    "phone": "+1-555-0100",
    "coaches": ["Coach Taylor"],
    "players": ["Sarah Jenkins", "Mike Johnson"],
}

TEAM_LIST_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Teams loaded successfully",
    "status": "ready",
    "description": "Organization teams for the Team Listing screen",
    "link": None,
    "error": None,
    "organization": "Seeded Hoops Club",
    "items": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Varsity Squad",
            "age_group": "U16",
            "email": "coach.taylor@school.edu",
            "status": "active",
            "coaches": ["John Doe"],
            "players": ["Player One", "Player Two"],
            "description": "Team Details",
        }
    ],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False,
    },
}

TEAM_SEARCH_RESPONSE_EXAMPLE = {
    **TEAM_LIST_RESPONSE_EXAMPLE,
    "search_query": "Varsity",
    "message": "Teams matching your search",
}


class TeamNamedMemberInput(BaseModel):
    """Named roster member from the Team Listing create form."""

    name: str = Field(
        description="Coach or player display name",
        examples=["John Doe"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Normalize member display name."""
        return value.strip()


class TeamListItem(BaseModel):
    """Single team row for list and search responses."""

    id: UUID = Field(description="Team UUID")
    name: str = Field(description="Team display name")
    age_group: str | None = Field(default=None, description="Age group label")
    email: str | None = Field(
        default=None,
        description="Primary coach contact email when assigned",
    )
    status: str = Field(default="active", description="Team lifecycle status")
    coaches: list[str] = Field(
        default_factory=list,
        description="Coach display names assigned to the team",
    )
    players: list[str] = Field(
        default_factory=list,
        description="Player display names on the roster",
    )
    description: str | None = Field(default=None, description="Team description")


class TeamListResponse(BaseModel):
    """Paginated team list for GET /teams."""

    model_config = ConfigDict(json_schema_extra={"example": TEAM_LIST_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    items: list[TeamListItem] = Field(default_factory=list)
    pagination: PaginationMeta


class TeamSearchResponse(BaseModel):
    """Team search results for GET /teams/search."""

    model_config = ConfigDict(json_schema_extra={"example": TEAM_SEARCH_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    search_query: str = Field(description="Normalized search term used for filtering")
    items: list[TeamListItem] = Field(default_factory=list)
    pagination: PaginationMeta


class TeamCreateRequest(BaseModel):
    """Payload for POST /teams (Team Listing and Team Details flows)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [TEAM_LISTING_CREATE_EXAMPLE, TEAM_DETAILS_CREATE_EXAMPLE]
        }
    )

    name: str = Field(
        description="Team display name",
        examples=["Varsity Squad"],
    )
    email: str | None = Field(
        default=None,
        description=(
            "Primary coach contact email (required for Team Details create; "
            "optional for Team Listing create)"
        ),
        examples=["coach.taylor@school.edu"],
    )
    season: str | None = Field(
        default=None,
        description="Competition season label",
        examples=["2025-2026"],
    )
    home_ground: str | None = Field(
        default=None,
        description="Home venue or facility name",
        examples=["Main Gymnasium"],
    )
    age_group: str | None = Field(
        default=None,
        description="Age group label for the roster",
        examples=["16-18"],
    )
    training_schedule: str | None = Field(
        default=None,
        description="Weekly practice schedule summary",
        examples=["Mon/Wed 4:00 PM"],
    )
    founded: date | None = Field(
        default=None,
        description="Team founding date",
        examples=["2018-09-01"],
    )
    phone: str | None = Field(
        default=None,
        description="Figma Phone metadata from the status bar (not persisted on the team row)",
        examples=["+1-555-0100"],
    )
    coaches: list[TeamNamedMemberInput | str] = Field(
        default_factory=list,
        description="Coach display names for the Team Listing create form",
    )
    players: list[TeamNamedMemberInput | str] = Field(
        default_factory=list,
        description="Player display names for the Team Listing create form",
    )

    @field_validator("name", "email", "season", "home_ground", "age_group", "training_schedule")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        """Normalize string fields."""
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def normalize_member_names(self) -> Self:
        """Normalize coach and player payloads to trimmed display names."""
        object.__setattr__(self, "coach_names", _extract_member_names(self.coaches))
        object.__setattr__(self, "player_names", _extract_member_names(self.players))
        return self


def _extract_member_names(values: list[TeamNamedMemberInput | str]) -> list[str]:
    """Convert string or `{name}` roster entries into trimmed display names."""
    names: list[str] = []
    for item in values:
        if isinstance(item, str):
            cleaned = item.strip()
        else:
            cleaned = item.name.strip()
        if cleaned:
            names.append(cleaned)
    return names


class TeamUpdateRequest(BaseModel):
    """Payload for PUT /teams/{team_id}."""

    model_config = ConfigDict(json_schema_extra={"example": TEAM_DETAILS_UPDATE_EXAMPLE})

    name: str | None = Field(default=None, description="Updated team display name")
    email: str | None = Field(
        default=None,
        description="Updated primary coach email (Figma Coach_Email field)",
    )
    season: str | None = Field(default=None, description="Updated competition season")
    home_ground: str | None = Field(default=None, description="Updated home venue")
    age_group: str | None = Field(default=None, description="Updated age group label")
    training_schedule: str | None = Field(
        default=None,
        description="Updated training schedule summary",
    )
    founded: date | None = Field(default=None, description="Updated founding date")
    phone: str | None = Field(
        default=None,
        description="Figma Phone metadata (not persisted on the team row)",
    )
    role: str | None = Field(
        default=None,
        description="Updated primary coach role label",
        examples=["head_coach"],
    )
    coaches: list[str] | None = Field(
        default=None,
        description="Replacement coach display names (metadata only)",
    )
    players: list[str] | None = Field(
        default=None,
        description="Replacement player display names (metadata only)",
    )

    @field_validator(
        "name",
        "email",
        "season",
        "home_ground",
        "age_group",
        "training_schedule",
        "role",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional string fields."""
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        """Ensure the update body is not empty."""
        if all(
            value is None
            for value in (
                self.name,
                self.email,
                self.season,
                self.home_ground,
                self.age_group,
                self.training_schedule,
                self.founded,
                self.phone,
                self.role,
                self.coaches,
                self.players,
            )
        ):
            raise ValueError("At least one field must be provided to update a team")
        return self


class TeamDetailsResponse(BaseModel):
    """Team Details screen response envelope."""

    model_config = ConfigDict(json_schema_extra={"example": TEAM_DETAILS_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="active", description="Team lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Team UUID")
    name: str = Field(description="Team display name")
    season: str | None = Field(default=None, description="Competition season")
    home_ground: str | None = Field(default=None, description="Home venue or facility")
    coaches: list[str] = Field(
        default_factory=list,
        description="Coach display names assigned to the team",
    )
    players: list[str] = Field(
        default_factory=list,
        description="Player display names on the roster",
    )
    founded: date | None = Field(default=None, description="Team founding date when available")
    age_group: str | None = Field(default=None, description="Age group label")
    training_schedule: str | None = Field(
        default=None,
        description="Weekly practice schedule summary",
    )
    phone: str | None = Field(
        default=None,
        description="Echo of primary coach phone for Figma Phone field display",
    )
    phone_number: str | None = Field(
        default=None,
        description="Stored primary coach phone from the linked user account",
    )
    email: str | None = Field(
        default=None,
        description="Primary coach contact email (Figma Coach_Email field)",
    )
    role: str | None = Field(
        default=None,
        description="Primary coach role label",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Distinct coach role labels assigned to the team",
    )
    organization: str = Field(description="Organization display name")
    created_at: datetime | None = None
