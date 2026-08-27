"""Pydantic schemas for coach leaderboard APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.profile import CoachProfileData, ProfileImageResponse

LEADERBOARD_SEARCH_REQUEST_EXAMPLE = {
    "search_query": "Jane",
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}


class LeaderboardSearchRequest(BaseModel):
    """Payload for POST /leaderboard/search."""

    model_config = ConfigDict(json_schema_extra={"example": LEADERBOARD_SEARCH_REQUEST_EXAMPLE})

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


class LeaderboardPlayerItem(BaseModel):
    """One ranked player row on the leaderboard screen."""

    rank: int = Field(description="1-based leaderboard rank", examples=[1])
    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Display name for leaderboard cards", examples=["Jane Doe"])
    full_name: str = Field(description="Player full name from Figma name container", examples=["Jane Doe"])
    shooting_percent: int = Field(description="Shooting percentage (0-100)", examples=[62])
    attempts: int = Field(description="Total shot attempts", examples=[24])
    makes: int = Field(description="Total makes", examples=[15])


class LeaderboardListResponse(BaseModel):
    """Leaderboard list response shared by list, search, and filter endpoints."""

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
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "Jane Doe",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": None,
                "username": None,
                "phone": None,
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
                        "shooting_percent": 62,
                        "attempts": 24,
                        "makes": 15,
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
    id: UUID | None = Field(
        default=None,
        description="Top-ranked player id when items are present, otherwise null",
    )
    name: str | None = Field(default=None, description="Top-ranked player display name")
    first_name: str | None = Field(default=None, description="Top-ranked player first name")
    last_name: str | None = Field(default=None, description="Top-ranked player last name")
    email: EmailStr | None = Field(default=None, description="Optional coach context email")
    username: str | None = Field(default=None, description="Optional coach context username")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    phone_number: str | None = Field(default=None, description="Optional coach contact phone")
    profile: CoachProfileData | None = Field(
        default=None,
        description="Optional nested profile context for shared mobile layout components",
    )
    avatar: ProfileImageResponse | None = Field(default=None, description="Optional profile avatar")
    address: str | None = Field(default=None, description="Optional address for profile chrome")
    items: list[LeaderboardPlayerItem] = Field(default_factory=list)
