"""Pydantic schemas for One Drill Step-3 session management."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ONE_DRILL_SESSION_CREATE_EXAMPLE = {
    "player": "Charlie Hudson",
    "drill": "3-Point Shooting",
    "makes": 5,
    "attempts": 10,
    "free_throws_makes": 2,
    "free_throws_attempts": 3,
    "phone": "+1-555-0100",
}

ONE_DRILL_SESSION_UPDATE_EXAMPLE = {
    "makes": 7,
    "attempts": 12,
    "free_throws_makes": 3,
    "free_throws_attempts": 4,
    "phone": "+1-555-0100",
}


class OneDrillSessionCreateRequest(BaseModel):
    """Payload for creating a One Drill Step-3 session with performance metrics."""

    model_config = ConfigDict(json_schema_extra={"example": ONE_DRILL_SESSION_CREATE_EXAMPLE})

    player: str = Field(
        ...,
        description="Selected player full name",
        examples=["Charlie Hudson"],
    )
    drill: str = Field(
        ...,
        description="Selected drill name",
        examples=["3-Point Shooting"],
    )
    makes: int = Field(
        ...,
        ge=0,
        description="Field-goal makes recorded for the drill",
        examples=[5],
    )
    attempts: int = Field(
        ...,
        ge=0,
        description="Field-goal attempts recorded for the drill",
        examples=[10],
    )
    free_throws_makes: int = Field(
        default=0,
        ge=0,
        description="Free throw makes recorded during the session",
        examples=[2],
    )
    free_throws_attempts: int = Field(
        default=0,
        ge=0,
        description="Free throw attempts recorded during the session",
        examples=[3],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class OneDrillSessionUpdateRequest(BaseModel):
    """Payload for updating One Drill Step-3 session metrics."""

    model_config = ConfigDict(json_schema_extra={"example": ONE_DRILL_SESSION_UPDATE_EXAMPLE})

    makes: int | None = Field(
        default=None,
        ge=0,
        description="Updated field-goal makes",
        examples=[7],
    )
    attempts: int | None = Field(
        default=None,
        ge=0,
        description="Updated field-goal attempts",
        examples=[12],
    )
    free_throws_makes: int | None = Field(
        default=None,
        ge=0,
        description="Updated free throw makes",
        examples=[3],
    )
    free_throws_attempts: int | None = Field(
        default=None,
        ge=0,
        description="Updated free throw attempts",
        examples=[4],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class OneDrillSessionResponse(BaseModel):
    """One Drill Step-3 session detail returned after create, get, or update."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session saved successfully",
                "status": "saved",
                "description": "One Drill session metrics recorded",
                "link": "/api/v1/sessions/summary",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "player": "Charlie Hudson",
                "drill": "3-Point Shooting",
                "makes": 5,
                "attempts": 10,
                "free_throws_makes": 2,
                "free_throws_attempts": 3,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(description="Session save state for the mobile UI")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Practice session identifier")
    player: str = Field(description="Selected player full name")
    drill: str = Field(description="Selected drill name")
    makes: int = Field(description="Field-goal makes")
    attempts: int = Field(description="Field-goal attempts")
    free_throws_makes: int = Field(description="Free throw makes")
    free_throws_attempts: int = Field(description="Free throw attempts")


class OneDrillSessionSummaryItem(BaseModel):
    """Summary row for one saved One Drill session."""

    id: UUID = Field(description="Practice session identifier")
    player: str = Field(description="Player full name", examples=["Charlie Hudson"])
    drill: str = Field(description="Drill name", examples=["3-Point Shooting"])
    makes: int = Field(description="Field-goal makes", examples=[5])
    attempts: int = Field(description="Field-goal attempts", examples=[10])
    free_throws_makes: int = Field(description="Free throw makes", examples=[2])
    free_throws_attempts: int = Field(description="Free throw attempts", examples=[3])
    status: str = Field(description="Session lifecycle status", examples=["in_progress"])


class OneDrillSessionsSummaryResponse(BaseModel):
    """List of One Drill session summaries for the authenticated coach."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session summaries loaded successfully",
                "status": "ready",
                "description": "Review saved One Drill sessions",
                "link": None,
                "error": None,
                "id": None,
                "sessions": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "player": "Charlie Hudson",
                        "drill": "3-Point Shooting",
                        "makes": 5,
                        "attempts": 10,
                        "free_throws_makes": 2,
                        "free_throws_attempts": 3,
                        "status": "in_progress",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID | None = Field(
        default=None,
        description="Optional identifier when a single session context applies",
    )
    sessions: list[OneDrillSessionSummaryItem] = Field(default_factory=list)
