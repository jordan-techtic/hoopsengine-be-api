"""Pydantic schemas for organization admin leaderboard APIs (HE-404)."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.leaderboard import LeaderboardPlayerItem
from app.schemas.profile import CoachProfileData, ProfileImageResponse

ORG_ADMIN_LEADERBOARD_FILTER_REQUEST_EXAMPLE = {
    "filters": {
        "ranking": "top",
        "date_range": {
            "start": "2026-01-01",
            "end": "2026-12-31",
        },
    },
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}

ORG_ADMIN_LEADERBOARD_SEARCH_QUERY_EXAMPLE = {
    "search_query": "Jane",
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}


class OrgAdminLeaderboardFilterDateRange(BaseModel):
    """Inclusive date range for leaderboard performance filtering."""

    start: date = Field(
        description="Start date (YYYY-MM-DD) for session statistics",
        examples=["2026-01-01"],
    )
    end: date = Field(
        description="End date (YYYY-MM-DD) for session statistics",
        examples=["2026-12-31"],
    )

    @model_validator(mode="after")
    def validate_range(self) -> OrgAdminLeaderboardFilterDateRange:
        """Ensure the start date is not after the end date."""
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        return self


class OrgAdminLeaderboardFilters(BaseModel):
    """Ranking filter pills for the org-admin leaderboard screen."""

    ranking: Literal["top", "bottom"] = Field(
        description="Show top performers or bottom performers",
        examples=["top"],
    )
    date_range: OrgAdminLeaderboardFilterDateRange | None = Field(
        default=None,
        description="Optional inclusive date range limiting session statistics",
    )


class OrgAdminLeaderboardFilterRequest(BaseModel):
    """Payload for POST /admin/leaderboard/filters."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_LEADERBOARD_FILTER_REQUEST_EXAMPLE},
    )

    filters: OrgAdminLeaderboardFilters = Field(
        description="Ranking and optional date-range filters",
    )
    full_name: str | None = Field(
        default=None,
        description="Optional Figma name container metadata (not used for filtering)",
        examples=["Jane Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        """Normalize optional full_name metadata."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrgAdminLeaderboardSearchRequest(BaseModel):
    """Query parameters for GET /admin/leaderboard/search."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_LEADERBOARD_SEARCH_QUERY_EXAMPLE},
    )

    search_query: str | None = Field(
        default=None,
        description="Player name search text (required unless full_name is provided)",
        examples=["Jane"],
    )
    full_name: str | None = Field(
        default=None,
        description="Figma name container field; used as search text when search_query is omitted",
        examples=["Jane Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("search_query", "full_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional search fields."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrgAdminLeaderboardListResponse(BaseModel):
    """Leaderboard list response for org-admin list, search, and filter endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Leaderboard loaded successfully",
                "status": "ready",
                "description": "Top players ranked by shooting percentage",
                "link": None,
                "error": None,
                "title": "Leaderboard",
                "organization": "Seeded Hoops Club",
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "Jane Doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": None,
                "username": None,
                "phone": "+1-555-0100",
                "phone_number": None,
                "profile": None,
                "avatar": None,
                "address": None,
                "items": [
                    {
                        "rank": 1,
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Jane Doe",
                        "full_name": "Jane Doe",
                        "shooting_percent": 80,
                        "attempts": 10,
                        "makes": 8,
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready", description="Screen state indicator for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    title: str = Field(default="Leaderboard", description="Screen title for the mobile client")
    organization: str | None = Field(
        default=None,
        description="Organization name for the authenticated org admin",
    )
    id: UUID | None = Field(
        default=None,
        description="Top-ranked player id when items are present, otherwise null",
    )
    name: str | None = Field(default=None, description="Top-ranked player display name")
    first_name: str | None = Field(default=None, description="Top-ranked player first name")
    last_name: str | None = Field(default=None, description="Top-ranked player last name")
    email: EmailStr | None = Field(default=None, description="Optional profile context email")
    username: str | None = Field(default=None, description="Optional profile context username")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    phone_number: str | None = Field(default=None, description="Optional contact phone")
    profile: CoachProfileData | None = Field(
        default=None,
        description="Optional nested profile context for shared mobile layout components",
    )
    avatar: ProfileImageResponse | None = Field(default=None, description="Optional profile avatar")
    address: str | None = Field(default=None, description="Optional address for profile chrome")
    items: list[LeaderboardPlayerItem] = Field(default_factory=list)
