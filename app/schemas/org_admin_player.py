"""Pydantic schemas for organization admin player management APIs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.player import PlayerListItem

ORG_ADMIN_PLAYER_STATS_EXAMPLE = {
    "games_played": 12,
    "goals": 24,
    "assists": 5,
    "yellow_cards": 1,
}

ORG_ADMIN_PLAYER_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Player details loaded successfully",
    "status": "ready",
    "description": "Player profile, statistics, and contact information",
    "title": "Player Management",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Ava Morales",
    "first_name": "Ava",
    "last_name": "Morales",
    "full_name": "Ava Morales",
    "email": "ava.morales@varsityacademy.com",
    "phone_number": "+1 (555) 382-9102",
    "phone": "+1 (555) 382-9102",
    "team": "Varsity Squad",
    "team_assignment": "Varsity Squad",
    "position": "Forward",
    "stats": ORG_ADMIN_PLAYER_STATS_EXAMPLE,
}

ORG_ADMIN_PLAYER_LIST_EXAMPLE = {
    "success": True,
    "message": "Players loaded successfully",
    "status": "ready",
    "description": "Active players in your organization",
    "title": "Player Management",
    "link": None,
    "error": None,
    "organization": "Seeded Hoops Club",
    "phone": "+1-555-0100",
    "players": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Ava Morales",
            "code": "PC-AVA001",
            "player_code": "PC-AVA001",
            "status": "active",
            "team": "Varsity Squad",
            "team_name": "Varsity Squad",
        }
    ],
}

ORG_ADMIN_PLAYER_SEARCH_REQUEST_EXAMPLE = {
    "player_code": "PC-AVA001",
    "name": "Ava Morales",
    "phone": "+1-555-0100",
}

ORG_ADMIN_PLAYER_SEARCH_RESPONSE_EXAMPLE = {
    **ORG_ADMIN_PLAYER_LIST_EXAMPLE,
    "message": "Player search completed successfully",
    "description": "Players matching player code 'PC-AVA001'",
    "player_code": "PC-AVA001",
}

ORG_ADMIN_PLAYER_STATUS_REQUEST_EXAMPLE = {
    "status": "inactive",
    "phone": "+1-555-0100",
}

ORG_ADMIN_PLAYER_STATUS_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Player status updated successfully",
    "status": "inactive",
    "description": "Player roster status was updated",
    "title": "Player Management",
    "link": None,
    "error": None,
    "organization": "Seeded Hoops Club",
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Ava Morales",
    "code": "PC-AVA001",
    "player_code": "PC-AVA001",
    "team": "Varsity Squad",
    "phone": "+1-555-0100",
}


class OrgAdminPlayerStats(BaseModel):
    """Aggregated player statistics for the org-admin Player Details screen."""

    games_played: int = Field(default=0, description="Distinct sessions with recorded stats")
    goals: int = Field(default=0, description="Total makes mapped for the statistics cards")
    assists: int = Field(default=0, description="Assists (not tracked — returns 0)")
    yellow_cards: int = Field(default=0, description="Discipline count (not tracked — returns 0)")


class OrgAdminPlayerDetailResponse(BaseModel):
    """Player detail response for the Organization Admin Player Details screen."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="Player Management")
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Player full display name")
    first_name: str = Field(description="Player first name")
    last_name: str = Field(description="Player last name")
    full_name: str = Field(description="Figma Name field (`full_name`)")
    email: str | None = Field(default=None, description="Contact email (Coach_Email in Figma)")
    phone_number: str | None = Field(
        default=None,
        description="Stored contact phone number",
    )
    phone: str | None = Field(
        default=None,
        description="Echo of stored phone for Figma Phone field display",
    )
    team: str | None = Field(default=None, description="Team display name")
    team_assignment: str | None = Field(
        default=None,
        description="Figma Team Assignment field (team display name)",
    )
    position: str | None = Field(default=None, description="Player position label")
    stats: OrgAdminPlayerStats = Field(description="Aggregated player statistics")


class OrgAdminPlayerListItem(BaseModel):
    """Summary row for the Organization Admin Player Listing screen (HE-424)."""

    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Player full display name")
    code: str | None = Field(default=None, description="Player code alias for mobile cards")
    player_code: str | None = Field(default=None, description="Unique player code")
    status: Literal["active", "inactive"] = Field(description="Roster status badge value")
    team: str | None = Field(default=None, description="Associated team display name")
    team_name: str | None = Field(
        default=None,
        description="Same as team — retained for backward compatibility",
    )


class OrgAdminPlayerListResponse(BaseModel):
    """Response for GET /admin/players (Player Listing screen)."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_LIST_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="Player Management")
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    players: list[OrgAdminPlayerListItem] = Field(default_factory=list)


class OrgAdminPlayerSearchRequest(BaseModel):
    """Payload for POST /admin/players/search."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_SEARCH_REQUEST_EXAMPLE})

    player_code: str = Field(
        description="Player code to search for (required)",
        examples=["PC-AVA001"],
    )
    name: str | None = Field(
        default=None,
        description="Optional Figma name container metadata (not used for filtering)",
        examples=["Ava Morales"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("player_code")
    @classmethod
    def strip_player_code(cls, value: str) -> str:
        """Normalize player code search input."""
        return value.strip()


class OrgAdminPlayerSearchResponse(BaseModel):
    """Response for POST /admin/players/search."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_SEARCH_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="Player Management")
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    player_code: str = Field(description="Normalized player code used for the search")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    players: list[OrgAdminPlayerListItem] = Field(default_factory=list)


class OrgAdminPlayerStatusUpdateRequest(BaseModel):
    """Payload for PATCH /admin/players/{player_id}/status."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_STATUS_REQUEST_EXAMPLE})

    status: Literal["active", "inactive"] = Field(
        description="Updated roster status for the player",
        examples=["active"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class OrgAdminPlayerStatusUpdateResponse(BaseModel):
    """Successful player status update response."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_STATUS_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: Literal["active", "inactive"] = Field(description="Updated player roster status")
    description: str | None = None
    title: str = Field(default="Player Management")
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Player full display name")
    code: str | None = Field(default=None, description="Player code alias")
    player_code: str | None = Field(default=None, description="Unique player code")
    team: str | None = Field(default=None, description="Associated team display name")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )


ORG_ADMIN_PLAYER_REMOVAL_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Confirm player removal",
    "status": "confirm",
    "description": "Are you sure you want to delete this coach? This action is permanent.",
    "title": "Remove Player",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "player_id": "11111111-2222-3333-4444-555555555555",
    "name": "Jane Doe",
    "full_name": "Jane Doe",
    "email": "sarah.jenkins@school.edu",
    "phone_number": "(555) 123-4567",
    "phone": "(555) 123-4567",
    "team": "Varsity Squad",
    "organization": "Varsity Academy",
    "confirmation_message": "Are you sure you want to delete this coach? This action is permanent.",
}

ORG_ADMIN_PLAYER_REMOVAL_REQUEST_EXAMPLE = {
    "full_name": "Jane Doe",
    "email": "sarah.jenkins@school.edu",
    "phone": "(555) 123-4567",
}

ORG_ADMIN_PLAYER_REMOVAL_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Player removed successfully",
    "status": "removed",
    "description": "The player was removed from the organization",
    "title": "Remove Player",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "player_id": "11111111-2222-3333-4444-555555555555",
    "name": "Jane Doe",
    "full_name": "Jane Doe",
    "email": "sarah.jenkins@school.edu",
    "phone": "(555) 123-4567",
    "organization": "Varsity Academy",
}


class OrgAdminPlayerRemovalDetailResponse(BaseModel):
    """Player detail response for the Organization Admin Remove Player confirmation screen."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_REMOVAL_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="confirm")
    description: str = Field(description="Permanent deletion confirmation copy for the modal")
    title: str = Field(default="Remove Player")
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Player UUID")
    player_id: UUID = Field(description="Same as id — bound for mobile detail screens")
    name: str = Field(description="Player full display name")
    full_name: str = Field(description="Figma Name field (`full_name`)")
    email: str | None = Field(default=None, description="Player contact email")
    phone_number: str | None = Field(default=None, description="Stored contact phone number")
    phone: str | None = Field(
        default=None,
        description="Echo of stored phone for Figma Phone field display",
    )
    team: str | None = Field(default=None, description="Team assignment display name")
    organization: str = Field(description="Organization display name")
    confirmation_message: str = Field(
        description="Exact confirmation modal copy shown before removal",
    )


class OrgAdminPlayerRemovalRequest(BaseModel):
    """Payload for DELETE /admin/players/{player_id}."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_REMOVAL_REQUEST_EXAMPLE})

    full_name: str = Field(
        description="Player full name used to confirm removal (Figma Name field)",
        examples=["Jane Doe"],
    )
    email: str = Field(
        description="Player contact email used to confirm removal (Figma Email field)",
        examples=["sarah.jenkins@school.edu"],
    )
    phone: str = Field(
        description="Player contact phone used to confirm removal (Figma Phone field)",
        examples=["(555) 123-4567"],
    )


class OrgAdminPlayerRemovalResponse(BaseModel):
    """Successful player removal response for organization admins."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PLAYER_REMOVAL_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="removed")
    description: str | None = None
    title: str = Field(default="Remove Player")
    link: str | None = None
    error: None = None
    id: UUID
    player_id: UUID
    name: str
    full_name: str
    email: str
    phone: str
    organization: str = Field(description="Organization display name")
