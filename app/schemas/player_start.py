"""Pydantic schemas for player Start screen APIs (HE-229)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

PLAYER_START_DRILL_EXAMPLE = {
    "name": "Catch & Shoot From Wing",
    "duration": 10,
}

PLAYER_START_GET_EXAMPLE = {
    "success": True,
    "message": "Workout start data loaded successfully",
    "status": "ready",
    "description": "Ready to train? Review today's drills and quick stats before starting.",
    "link": None,
    "error": None,
    "workout_id": None,
    "phone": "+1-555-0100",
    "statistics": {
        "total_sessions": 12,
        "total_attempts": 240,
        "shooting_percentage": "45.0%",
        "drill_count": 2,
        "total_duration_minutes": 18,
    },
    "drills": [
        {"name": "Warm-up Lap", "duration": 10},
        {"name": "3-Point Corner", "duration": 8},
    ],
}

PLAYER_START_POST_EXAMPLE = {
    "success": True,
    "message": "Workout started successfully",
    "status": "started",
    "description": "Your workout session is ready",
    "link": None,
    "error": None,
    "workout_id": "11111111-2222-3333-4444-555555555555",
    "phone": "+1-555-0100",
    "drills": [
        {"name": "Catch & Shoot From Wing", "duration": 10},
        {"name": "Cone Slasher Layup Finishing", "duration": 8},
    ],
}

PLAYER_START_REQUEST_EXAMPLE = {
    "workout_id": None,
    "drills": [
        {"name": "Catch & Shoot From Wing", "duration": 10},
        {"name": "Cone Slasher Layup Finishing", "duration": 8},
    ],
    "phone": "+1-555-0100",
}


class PlayerStartDrillItem(BaseModel):
    """One drill in today's workout schedule."""

    name: str = Field(
        description="Drill display name",
        examples=["Catch & Shoot From Wing"],
    )
    duration: int = Field(
        description="Planned drill duration in minutes",
        examples=[10],
        ge=1,
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        """Reject blank drill names at the schema layer."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Drill name is required")
        return cleaned


class PlayerStartStatistics(BaseModel):
    """Aggregate workout statistics shown on the Start screen."""

    total_sessions: int = Field(description="Total completed workout sessions", examples=[12], ge=0)
    total_attempts: int = Field(description="Lifetime shot attempts recorded", examples=[240], ge=0)
    shooting_percentage: str = Field(
        description="Aggregate field-goal shooting percentage",
        examples=["45.0%"],
    )
    drill_count: int = Field(description="Number of drills scheduled for today", examples=[2], ge=0)
    total_duration_minutes: int = Field(
        description="Combined planned duration of today's drills in minutes",
        examples=[18],
        ge=0,
    )


class PlayerStartWorkoutRequest(BaseModel):
    """Payload for POST /player/start."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_START_REQUEST_EXAMPLE})

    workout_id: UUID | None = Field(
        default=None,
        description="Optional existing workout UUID (reserved for future resume flows)",
        examples=[None],
    )
    drills: list[PlayerStartDrillItem] | None = Field(
        default=None,
        description="Today's drill list to start the workout with",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerStartGetResponse(MobileWriteOnlyPasswordMixin):
    """GET /player/start response with statistics and today's drill list."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_START_GET_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    workout_id: UUID | None = Field(
        default=None,
        description="Today's in-progress workout session UUID when one exists",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata echoed from the request (not persisted)",
        examples=["+1-555-0100"],
    )
    statistics: PlayerStartStatistics
    drills: list[PlayerStartDrillItem] = Field(default_factory=list)


class PlayerStartPostResponse(MobileWriteOnlyPasswordMixin):
    """POST /player/start response after creating a workout session."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_START_POST_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: Literal["started"] = Field(default="started")
    description: str | None = None
    link: str | None = None
    error: None = None
    workout_id: UUID = Field(description="Created workout session UUID")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata echoed from the request (not persisted)",
        examples=["+1-555-0100"],
    )
    drills: list[PlayerStartDrillItem] = Field(default_factory=list)
