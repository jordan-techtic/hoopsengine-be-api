"""Pydantic schemas for organization admin coach invite and search APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ORG_ADMIN_INVITE_COACH_REQUEST_EXAMPLE = {
    "email": "ava.morales@academy.org",
    "phone": "+1-555-0100",
    "company": "Acme Realty",
}

ORG_ADMIN_INVITE_COACH_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Coach invitation sent successfully",
    "status": "invited",
    "description": "An invitation email was sent to the coach",
    "link": "http://localhost:3000/coach/invite?token=example-token",
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "email": "ava.morales@academy.org",
    "organization": "Courtside Elite Academy",
    "address": "1 Court Ave",
    "roles": ["coach"],
}

ORG_ADMIN_SEARCH_COACHES_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Coaches loaded successfully",
    "status": "ready",
    "description": "Organization coaches matching your search",
    "link": None,
    "error": None,
    "organization": "Courtside Elite Academy",
    "address": "1 Court Ave",
    "roles": ["coach"],
    "search_query": "Ava",
    "coaches": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Ava Morales",
            "email": "ava.morales@academy.org",
            "status": "invited",
            "role": "subteam_coach",
        }
    ],
}


class OrgAdminInviteCoachRequest(BaseModel):
    """Payload for POST /admin/invite-coach."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_INVITE_COACH_REQUEST_EXAMPLE})

    email: str = Field(
        description="Coach email address to invite to the organization",
        examples=["ava.morales@academy.org"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    company: str | None = Field(
        default=None,
        description="Optional client metadata from the Figma company field (not persisted)",
        examples=["Acme Realty"],
    )


class OrgAdminInviteCoachResponse(BaseModel):
    """Response for POST /admin/invite-coach."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_INVITE_COACH_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="invited", description="Invitation lifecycle status")
    description: str | None = None
    link: str | None = Field(
        default=None,
        description="Coach invitation link included when an invite token is generated",
    )
    error: None = None
    id: UUID = Field(description="Invited coach UUID from the client-domain coaches table")
    email: str = Field(description="Invited coach email address")
    organization: str = Field(description="Organization display name")
    address: str | None = Field(default=None, description="Organization address")
    roles: list[str] = Field(
        default_factory=lambda: ["coach"],
        description="Roles assigned to the invited coach account",
    )


class OrgAdminCoachSearchItem(BaseModel):
    """Coach entry returned by the Invite Coach search endpoint."""

    id: UUID = Field(description="Coach UUID")
    name: str = Field(description="Coach display name")
    email: str | None = Field(default=None, description="Coach contact email")
    status: str = Field(
        description="Invitation or membership status (`invited` or `active`)",
        examples=["invited"],
    )
    role: str | None = Field(default=None, description="Coach role within the organization")


class OrgAdminSearchCoachesResponse(BaseModel):
    """Response for GET /admin/search-coaches."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_SEARCH_COACHES_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    organization: str = Field(description="Organization display name")
    address: str | None = Field(default=None, description="Organization address")
    roles: list[str] = Field(
        default_factory=lambda: ["coach"],
        description="Coach roles available in the organization roster",
    )
    search_query: str | None = Field(
        default=None,
        description="Normalized search text used to filter coaches",
    )
    coaches: list[OrgAdminCoachSearchItem] = Field(default_factory=list)
