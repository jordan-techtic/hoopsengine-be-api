"""Pydantic schemas for coach Attendance APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ATTENDANCE_SEARCH_EXAMPLE = {
    "success": True,
    "message": "Players found",
    "status": "ready",
    "description": "Matching players for attendance",
    "link": None,
    "error": None,
    "search_query": "Alex",
    "full_name": "Alex",
    "players": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Alex Martinez",
            "jersey_number": "12",
            "status": "present",
        }
    ],
}

ATTENDANCE_SUMMARY_EXAMPLE = {
    "success": True,
    "message": "Attendance summary loaded",
    "status": "ready",
    "description": "Only present players will appear in recording",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Attendance",
    "title": "Attendance",
    "attendance_summary": {"present_count": 8, "total_count": 12},
    "players": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Alex Martinez",
            "jersey_number": "12",
            "status": "present",
        },
        {
            "id": "22222222-3333-4444-5555-666666666666",
            "name": "David Park",
            "jersey_number": "15",
            "status": "absent",
        },
    ],
}

ATTENDANCE_START_PRACTICE_REQUEST_EXAMPLE = {
    "present_player_ids": [
        "11111111-2222-3333-4444-555555555555",
        "22222222-3333-4444-5555-666666666666",
    ],
    "phone": "+1-555-0100",
}


class AttendancePlayerItem(BaseModel):
    """One player row on the Attendance screen."""

    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Full display name", examples=["Alex Martinez"])
    jersey_number: str | None = Field(
        default=None,
        description="Jersey number when assigned",
        examples=["12"],
    )
    status: str = Field(
        description="Attendance status for the current session",
        examples=["present"],
    )


class AttendanceSummaryCounts(BaseModel):
    """Present vs total player counts for the summary row."""

    present_count: int = Field(description="Number of players marked present", examples=[8])
    total_count: int = Field(description="Total active players in the roster", examples=[12])


class AttendanceStartPracticeRequest(BaseModel):
    """Payload for POST /attendance/start-practice."""

    model_config = ConfigDict(json_schema_extra={"example": ATTENDANCE_START_PRACTICE_REQUEST_EXAMPLE})

    present_player_ids: list[UUID] = Field(
        default_factory=list,
        description="Player UUIDs marked present when practice starts",
        examples=[["11111111-2222-3333-4444-555555555555"]],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class AttendancePlayerSearchResponse(BaseModel):
    """Search results for the Attendance player search input."""

    model_config = ConfigDict(json_schema_extra={"example": ATTENDANCE_SEARCH_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    search_query: str | None = Field(default=None, description="Normalized search text used")
    full_name: str | None = Field(default=None, description="Echo of Figma full_name search input")
    players: list[AttendancePlayerItem] = Field(default_factory=list)


class AttendanceSummaryResponse(BaseModel):
    """Attendance summary and player list for the Attendance screen."""

    model_config = ConfigDict(json_schema_extra={"example": ATTENDANCE_SUMMARY_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID | None = Field(default=None, description="Current attendance session UUID when available")
    name: str = Field(default="Attendance", description="Screen name for the mobile client")
    title: str = Field(default="Attendance", description="Screen title shown at the top of the Attendance UI")
    attendance_summary: AttendanceSummaryCounts
    players: list[AttendancePlayerItem] = Field(default_factory=list)


class AttendanceStartPracticeResponse(BaseModel):
    """Successful start-practice response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **ATTENDANCE_SUMMARY_EXAMPLE,
                "message": "Practice started successfully",
                "status": "in_progress",
                "session_id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="in_progress")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Started practice session UUID")
    name: str = Field(default="Attendance")
    title: str = Field(default="Attendance", description="Screen title shown at the top of the Attendance UI")
    session_id: UUID = Field(description="Same as id — practice session identifier")
    attendance_summary: AttendanceSummaryCounts
    players: list[AttendancePlayerItem] = Field(default_factory=list)
