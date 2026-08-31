"""Pydantic schemas for player Active Drill APIs (HE-455, HE-213)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

ActiveDrillPlaybackStatus = Literal["playing", "paused", "stopped"]
PlayerDrillStatus = Literal["playing", "paused", "stopped", "reset"]

PLAYER_DRILL_LIST_EXAMPLE = {
    "success": True,
    "message": "Drills loaded successfully",
    "status": "ready",
    "description": "Active drills assigned to your team",
    "link": None,
    "error": None,
    "phone": "+1-555-0100",
    "drills": [
        {
            "drill_id": "11111111-2222-3333-4444-555555555555",
            "name": "Warm-up Lap",
            "duration": 600,
            "status": "stopped",
            "time_remaining": "10:00",
        }
    ],
}

PLAYER_DRILL_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Drill details loaded successfully",
    "description": "Focus on form and pace throughout the drill",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "drill_id": "11111111-2222-3333-4444-555555555555",
    "name": "Warm-up Lap",
    "category": "general",
    "duration": 600,
    "status": "stopped",
    "timer": "00:00",
    "progress": 0,
    "time_remaining": "10:00",
    "phone": "+1-555-0100",
}

PLAYER_ACTIVE_DRILL_EXAMPLE = {
    "success": True,
    "message": "Drill playback started successfully",
    "description": "Active drill session",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Warm-up Lap",
    "timer": "00:00",
    "status": "playing",
    "progress": 0,
    "phone": "+1-555-0100",
}

PLAYER_DRILL_TIMER_EXAMPLE = {
    "success": True,
    "message": "Timer started successfully",
    "status": "playing",
    "description": "Active drill timer",
    "link": None,
    "error": None,
    "drill_id": "11111111-2222-3333-4444-555555555555",
    "time_remaining": "09:45",
    "phone": "+1-555-0100",
}


class PlayerDrillListItem(BaseModel):
    """One active drill in the player's assigned list."""

    drill_id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    duration: int = Field(description="Drill duration in seconds", examples=[600], ge=0)
    status: PlayerDrillStatus = Field(
        description="Current timer playback status for this drill",
        examples=["stopped"],
    )
    time_remaining: str = Field(
        description="Remaining time formatted as MM:SS",
        examples=["10:00"],
    )


class PlayerDrillListResponse(MobileWriteOnlyPasswordMixin):
    """List of active drills for the authenticated player."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_DRILL_LIST_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    drills: list[PlayerDrillListItem] = Field(default_factory=list)


class PlayerDrillDetailResponse(MobileWriteOnlyPasswordMixin):
    """Detailed active drill state for a single drill."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_DRILL_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    description: str | None = None
    link: str | None = None
    error: None = None
    drill_id: UUID
    name: str
    category: str
    duration: int = Field(ge=0)
    time_remaining: str = Field(description="Remaining time formatted as MM:SS")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )
    status: PlayerDrillStatus = Field(
        description="Current timer playback status",
        examples=["stopped"],
    )
    id: UUID = Field(description="Drill UUID (same as drill_id)")
    timer: str = Field(description="Elapsed time formatted as MM:SS", examples=["00:00"])
    progress: int = Field(description="Completion percentage (0-100)", examples=[0], ge=0, le=100)


class PlayerDrillPlayRequest(BaseModel):
    """Payload for POST /player/drills/{id}/play."""

    model_config = ConfigDict(json_schema_extra={"example": {"phone": "+1-555-0100"}})

    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerDrillTimerUpdateRequest(BaseModel):
    """Payload for PUT /player/drills/{id}/timer."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timer": "01:30",
                "status": "paused",
                "phone": "+1-555-0100",
            }
        }
    )

    timer: str = Field(
        description="Elapsed timer value formatted as MM:SS",
        examples=["01:30"],
    )
    status: ActiveDrillPlaybackStatus | None = Field(
        default=None,
        description="Optional playback status override (playing, paused, stopped)",
        examples=["paused"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("timer")
    @classmethod
    def validate_timer_format(cls, value: str) -> str:
        """Ensure timer matches MM:SS before service-level parsing."""
        cleaned = value.strip()
        parts = cleaned.split(":")
        if len(parts) != 2:
            raise ValueError("Timer must use MM:SS format")
        try:
            minutes = int(parts[0])
            seconds = int(parts[1])
        except ValueError as exc:
            raise ValueError("Timer must use MM:SS format") from exc
        if minutes < 0 or seconds < 0 or seconds >= 60:
            raise ValueError("Timer must use MM:SS format")
        return cleaned


class PlayerActiveDrillResponse(MobileWriteOnlyPasswordMixin):
    """Active Drill 2 playback response (HE-213)."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_ACTIVE_DRILL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    timer: str = Field(description="Elapsed time formatted as MM:SS", examples=["00:00"])
    status: ActiveDrillPlaybackStatus = Field(
        description="Current playback status",
        examples=["playing"],
    )
    progress: int = Field(description="Completion percentage (0-100)", examples=[40], ge=0, le=100)
    phone: str | None = Field(
        default=None,
        description="Optional client metadata echoed from the request (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerDrillTimerRequest(BaseModel):
    """Optional payload for player drill timer actions."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "drill_id": "11111111-2222-3333-4444-555555555555",
                "phone": "+1-555-0100",
            }
        }
    )

    drill_id: UUID | None = Field(
        default=None,
        description="Optional drill UUID to start; defaults to the current workout drill",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerDrillTimerResponse(MobileWriteOnlyPasswordMixin):
    """Timer action result for player active drills."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_DRILL_TIMER_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: Literal["playing", "stopped", "reset"] = Field(
        description="Timer status after the action",
        examples=["playing"],
    )
    description: str | None = None
    link: str | None = None
    error: None = None
    drill_id: UUID
    time_remaining: str = Field(description="Remaining time formatted as MM:SS")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata echoed from the request (not persisted)",
        examples=["+1-555-0100"],
    )
