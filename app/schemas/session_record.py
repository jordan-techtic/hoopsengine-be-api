"""Pydantic schemas for coach session mode selection and recording."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SessionMode

SESSION_RECORD_CREATE_EXAMPLE = {
    "session_mode": "one_drill",
    "drill_id": "11111111-2222-3333-4444-555555555555",
    "user_id": "22222222-3333-4444-5555-666666666666",
    "session_data": {
        "reps": 10,
        "time": "00:30:00",
        "performance": "good",
    },
    "session_details": {
        "description": "Focus on a single drill and track reps, time, or performance",
    },
    "phone": "+1-555-0100",
}


class OneDrillSessionDataInput(BaseModel):
    """Performance metrics captured when recording a One Drill session."""

    reps: int = Field(
        ...,
        ge=0,
        description="Number of repetitions completed",
        examples=[10],
    )
    time: str = Field(
        ...,
        description="Elapsed drill time (HH:MM:SS)",
        examples=["00:30:00"],
    )
    performance: str = Field(
        ...,
        description="Coach-assessed performance rating",
        examples=["good"],
    )


class SessionDetailsInput(BaseModel):
    """Optional nested details for the selected session mode."""

    description: str | None = Field(
        default=None,
        description="Coach-facing description or notes for this session mode selection",
        examples=["Focus on a single drill and track reps, time, or performance"],
    )


class SessionModeItem(BaseModel):
    """One selectable session mode shown on the Record Session screen."""

    mode: SessionMode = Field(
        description="Machine-readable session mode identifier",
        examples=[SessionMode.ONE_DRILL],
    )
    label: str = Field(
        description="Display label for the session mode option",
        examples=["One Drill"],
    )
    description: str = Field(
        description="Helper text explaining what this mode is for",
        examples=["Focus on a single drill and track reps, time, or performance"],
    )


class SessionModesResponse(BaseModel):
    """Available session modes for the Choose Your Session Mode screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session modes loaded successfully",
                "status": "ready",
                "description": "Choose a mode to begin recording your training session",
                "link": None,
                "error": None,
                "modes": [
                    {
                        "mode": "one_drill",
                        "label": "One Drill",
                        "description": "Focus on a single drill and track reps, time, or performance",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="ready", description="Screen state indicator for the mobile client")
    description: str | None = Field(
        default=None,
        description="Optional subtitle shown under the header",
    )
    link: str | None = Field(default=None, description="Optional in-app navigation target")
    error: None = Field(default=None, description="Always null on success")
    modes: list[SessionModeItem] = Field(description="Selectable session mode options")


class SessionModeDetailResponse(BaseModel):
    """Single session mode lookup response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session mode loaded successfully",
                "status": "ready",
                "description": "Focus on a single drill and track reps, time, or performance",
                "link": None,
                "error": None,
                "mode": {
                    "mode": "one_drill",
                    "label": "One Drill",
                    "description": "Focus on a single drill and track reps, time, or performance",
                },
            }
        }
    )

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable success message for the UI")
    status: str = Field(default="ready", description="Screen state indicator for the mobile client")
    description: str | None = Field(
        default=None,
        description="Mode helper text shown under the header",
    )
    link: str | None = Field(default=None, description="Optional in-app navigation target")
    error: None = Field(default=None, description="Always null on success")
    mode: SessionModeItem = Field(description="Requested session mode details")


class SessionRecordCreateRequest(BaseModel):
    """Payload for creating a session record after mode selection."""

    model_config = ConfigDict(json_schema_extra={"example": SESSION_RECORD_CREATE_EXAMPLE})

    session_mode: SessionMode = Field(
        ...,
        description="Selected session mode (required)",
        examples=[SessionMode.ONE_DRILL],
    )
    drill_id: UUID | None = Field(
        default=None,
        description="Selected drill UUID (required when session_mode is one_drill)",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    user_id: UUID | None = Field(
        default=None,
        description="Recording coach user UUID (defaults to authenticated user)",
        examples=["22222222-3333-4444-5555-666666666666"],
    )
    session_data: OneDrillSessionDataInput | None = Field(
        default=None,
        description="One Drill performance metrics (required when session_mode is one_drill)",
    )
    session_details: SessionDetailsInput | None = Field(
        default=None,
        description="Optional nested details such as a custom description",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class SessionRecordUpdateRequest(BaseModel):
    """Payload for updating an existing session record."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_mode": "daily_options",
                "session_details": {"description": "Pick from today's recommended drills"},
                "phone": "+1-555-0100",
            }
        }
    )

    session_mode: SessionMode | None = Field(
        default=None,
        description="Updated session mode",
        examples=[SessionMode.DAILY_OPTIONS],
    )
    session_details: SessionDetailsInput | None = Field(
        default=None,
        description="Updated session details",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class SessionRecordResponse(BaseModel):
    """Created or updated session record returned to the mobile client."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session mode recorded successfully",
                "status": "completed",
                "description": "Focus on a single drill and track reps, time, or performance",
                "link": "/coach/record/one-drill",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "One Drill",
                "session_mode": "one_drill",
                "session_details": {
                    "one_drill_quick_record": {
                        "quick_record": true,
                        "drill_id": "11111111-2222-3333-4444-555555555555",
                        "session_data": {"reps": 10, "time": "00:30:00", "performance": "good"},
                    }
                },
                "created_at": "2026-08-27T08:30:00Z",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(description="Current session lifecycle status")
    description: str | None = Field(
        default=None,
        description="Mode description or helper text for the UI",
    )
    link: str | None = Field(default=None, description="Suggested next navigation target")
    error: None = None
    id: UUID = Field(description="Practice session identifier")
    title: str | None = Field(
        default=None,
        description="Session mode display title for the mobile UI",
        examples=["One Drill"],
    )
    session_mode: SessionMode
    session_details: dict[str, Any] | None = None
    created_at: datetime | None = None
