"""Pydantic schemas for coach session summary and lifecycle actions."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SESSION_ACTION_REQUEST_EXAMPLE = {
    "phone": "+1-555-0100",
}


class SessionActionRequest(BaseModel):
    """Optional client metadata for session summary action endpoints."""

    model_config = ConfigDict(json_schema_extra={"example": SESSION_ACTION_REQUEST_EXAMPLE})

    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerStatItem(BaseModel):
    """Aggregated performance metrics for one player in a session."""

    player_name: str = Field(
        description="Player full name",
        examples=["Charlie Hudson"],
    )
    attempts: int = Field(description="Total field-goal attempts excluding free throws", examples=[10])
    makes: int = Field(description="Total field-goal makes excluding free throws", examples=[6])
    shooting_percent: int = Field(description="Shooting percentage (0-100)", examples=[60])
    free_throw_attempts: int = Field(description="Free throw attempts", examples=[5])
    free_throw_makes: int = Field(description="Free throw makes", examples=[4])
    free_throw_percent: int = Field(description="Free throw percentage (0-100)", examples=[80])


class SessionSummaryResponse(BaseModel):
    """Session summary payload for the Session Summary screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session summary loaded successfully",
                "status": "Session Complete! Nice work, coach",
                "description": "Review player performance metrics for this session",
                "link": "/coach/record/next-drill",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "session_id": "11111111-2222-3333-4444-555555555555",
                "player_stats": [
                    {
                        "player_name": "Charlie Hudson",
                        "attempts": 10,
                        "makes": 6,
                        "shooting_percent": 60,
                        "free_throw_attempts": 5,
                        "free_throw_makes": 4,
                        "free_throw_percent": 80,
                    }
                ],
                "session_time": "9:41",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(description="Section header / lifecycle message for the UI")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Practice session identifier (alias of session_id)")
    session_id: UUID
    player_stats: list[PlayerStatItem] = Field(default_factory=list)
    session_time: str = Field(description="Elapsed session time formatted as M:SS", examples=["9:41"])


class SessionActionResponse(BaseModel):
    """Response after advancing a drill or ending practice."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Advanced to the next drill",
                "status": "in_progress",
                "description": "Continue recording the current practice session",
                "link": "/coach/record/drill",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "session_id": "11111111-2222-3333-4444-555555555555",
                "current_drill_index": 1,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    session_id: UUID
    current_drill_index: int = Field(description="Zero-based index of the active drill")
