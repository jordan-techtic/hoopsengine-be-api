"""Pydantic schemas for authenticated player Home Screen APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class PlayerHomeRecentSessionItem(BaseModel):
    """One recent workout session row on the player Home screen."""

    session_name: str = Field(
        description="Display name for the workout session",
        examples=["Morning Shooting Block"],
    )
    attempts: int = Field(ge=0, description="Total field-goal attempts in the session", examples=[120])
    fg_percentage: str = Field(
        description="Field-goal shooting percentage for the session",
        examples=["57%"],
    )


class PlayerHomeProfileData(BaseModel):
    """Nested profile context for the Home screen header."""

    user_name: str = Field(description="Player display name", examples=["Lebron James"])
    team_name: str = Field(description="Team or organization display name", examples=["Los Angeles Lakers"])
    jersey_number: str = Field(description="Jersey number label", examples=["23"])


class PlayerHomeResponse(MobileWriteOnlyPasswordMixin):
    """Aggregated player home screen payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player home loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "title": "Home",
                "id": "00000000-0000-4000-8000-000000000033",
                "name": "Lebron James",
                "profile": {
                    "user_name": "Lebron James",
                    "team_name": "Los Angeles Lakers",
                    "jersey_number": "23",
                },
                "user_name": "Lebron James",
                "team_name": "Los Angeles Lakers",
                "jersey_number": "23",
                "total_sessions": 5,
                "total_attempts": 240,
                "recent_sessions": [
                    {
                        "session_name": "Morning Shooting Block",
                        "attempts": 120,
                        "fg_percentage": "57%",
                    },
                    {
                        "session_name": "Pre-Practice Tune Up",
                        "attempts": 180,
                        "fg_percentage": "62%",
                    },
                ],
                "motivational_card": "Earn your minutes. Own your moment.",
                "phone": "+1-555-0100",
                "company": "Acme Realty",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready", description="Screen state indicator for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    title: str = Field(default="Home", description="Screen title for the mobile client")
    id: UUID = Field(description="Player roster identifier")
    name: str = Field(description="Player display name for the home header")
    profile: PlayerHomeProfileData = Field(description="Nested profile fields for the home header")
    user_name: str = Field(description="Player display name")
    team_name: str = Field(description="Team or organization display name")
    jersey_number: str = Field(description="Jersey number label")
    total_sessions: int = Field(ge=0, description="Total completed workout sessions")
    total_attempts: int = Field(ge=0, description="Total field-goal attempts across sessions")
    recent_sessions: list[PlayerHomeRecentSessionItem] = Field(default_factory=list)
    motivational_card: str = Field(description="Motivational quote for the home card")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    company: str | None = Field(
        default=None,
        description="Optional organization label from Col_Organization (not persisted)",
    )
