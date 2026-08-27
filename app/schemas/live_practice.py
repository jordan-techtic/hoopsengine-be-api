"""Pydantic schemas for Live Practice APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

LIVE_PRACTICE_DRILL_CREATE_EXAMPLE = {
    "drill_name": "3-Point Corner",
    "duration": 60,
    "player_stats": [
        {"player_id": "11111111-2222-3333-4444-555555555555", "shots_made": 5, "shots_attempted": 10},
    ],
    "phone": "+1-555-0100",
}

RECORD_SHOTS_EXAMPLE = {
    "shots_made": 5,
    "shots_attempted": 10,
    "drill_id": "11111111-2222-3333-4444-555555555555",
    "phone": "+1-555-0100",
}


class LivePracticePlayerStatInput(BaseModel):
    """Optional per-player stat row included when saving a live practice drill."""

    player_id: str = Field(
        description="Player UUID",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    shots_made: int = Field(description="Shots made for the player", examples=[5], ge=0)
    shots_attempted: int = Field(description="Shots attempted for the player", examples=[10], ge=0)


class LivePracticeDrillCreateRequest(BaseModel):
    """Payload for POST /live_practice/drills."""

    model_config = ConfigDict(json_schema_extra={"example": LIVE_PRACTICE_DRILL_CREATE_EXAMPLE})

    drill_name: str = Field(description="Live practice drill name", examples=["3-Point Corner"])
    duration: int = Field(description="Drill duration in seconds", examples=[60], ge=1)
    player_stats: list[LivePracticePlayerStatInput] | None = Field(
        default=None,
        description="Optional player stat rows validated when provided",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class LivePracticeDrillUpdateRequest(BaseModel):
    """Payload for PUT /live_practice/drills/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "drill_name": "3-Point Corner",
                "duration": 90,
                "phone": "+1-555-0100",
            }
        }
    )

    drill_name: str | None = Field(default=None, description="Updated drill name")
    duration: int | None = Field(default=None, description="Updated duration in seconds", ge=1)
    player_stats: list[LivePracticePlayerStatInput] | None = Field(
        default=None,
        description="Optional player stat rows validated when provided",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata (not persisted)",
        examples=["+1-555-0100"],
    )


class LivePracticeTimerRequest(BaseModel):
    """Optional payload for timer start/stop endpoints."""

    model_config = ConfigDict(json_schema_extra={"example": {"phone": "+1-555-0100", "duration": 60}})

    duration: int | None = Field(
        default=None,
        description="Optional timer duration override in seconds",
        examples=[60],
        ge=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class LivePracticeRecordShotsRequest(BaseModel):
    """Payload for POST /live_practice/players/{player_id}/shots."""

    model_config = ConfigDict(json_schema_extra={"example": RECORD_SHOTS_EXAMPLE})

    shots_made: int = Field(description="Shots made", examples=[5], ge=0)
    shots_attempted: int = Field(description="Shots attempted", examples=[10], ge=0)
    drill_id: UUID | None = Field(
        default=None,
        description="Optional live practice drill UUID for the current session",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata (not persisted)",
        examples=["+1-555-0100"],
    )


class LivePracticeDrillItem(BaseModel):
    """One live practice drill."""

    id: UUID
    drill_name: str
    duration: int
    category: str = Field(default="live_practice")


class LivePracticeDrillResponse(BaseModel):
    """Single drill response."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    address: str | None = None
    id: UUID
    drill_name: str
    duration: int


class LivePracticeDrillListResponse(BaseModel):
    """Drill list response."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    address: str | None = None
    drills: list[LivePracticeDrillItem] = Field(default_factory=list)


class LivePracticeDeleteResponse(BaseModel):
    """Successful drill deletion response."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    address: str | None = None
    id: UUID


class LivePracticeTimerStatusResponse(BaseModel):
    """Timer status response."""

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    address: str | None = None
    id: UUID | None = Field(default=None, description="Live practice session UUID")
    timer_state: str = Field(description="Timer state: running or stopped")
    elapsed_seconds: int = Field(default=0, description="Elapsed seconds on the timer")
    duration_seconds: int | None = Field(default=None, description="Configured drill duration")


class LivePracticePlayerStatisticsResponse(BaseModel):
    """Player statistics for the active live practice session."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    address: str | None = None
    id: UUID = Field(description="Player UUID")
    player_id: UUID
    name: str | None = None
    shots_made: int = Field(default=0)
    shots_attempted: int = Field(default=0)
    shooting_percent: int = Field(default=0)


class LivePracticeRecordShotsResponse(LivePracticePlayerStatisticsResponse):
    """Successful shot recording response."""

    pass
