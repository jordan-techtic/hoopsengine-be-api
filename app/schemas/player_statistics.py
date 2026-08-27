"""Pydantic schemas for public player statistics API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class SessionHistoryItem(BaseModel):
    """One session entry in a player's statistics history."""

    session_name: str = Field(examples=["Drill & Attack"])
    date: str = Field(examples=["Oct 15, 2026"])
    performance: str = Field(examples=["18/30 (60%)"])


class PlayerStatisticsResponse(MobileWriteOnlyPasswordMixin):
    """Player statistics for the View Statistics screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player statistics loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000033",
                "name": "Jane Doe",
                "player_id": "00000000-0000-4000-8000-000000000033",
                "active_field_goals": 240,
                "shooting_percentage": "76.1%",
                "session_history": [
                    {
                        "session_name": "Drill & Attack",
                        "date": "Oct 15, 2026",
                        "performance": "18/30 (60%)",
                    }
                ],
                "full_name": "Jane Doe",
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Player identifier (same as player_id)")
    name: str = Field(description="Player display name for the identity badge")
    player_id: UUID
    active_field_goals: int = Field(ge=0)
    shooting_percentage: str
    session_history: list[SessionHistoryItem] = Field(default_factory=list)
    full_name: str
    phone: str | None = None
