"""Pydantic schemas for coach sync activity APIs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncActivityItem(BaseModel):
    """One recent sync activity row."""

    title: str = Field(examples=["Practice Session synced successfully"])
    time: str = Field(examples=["2:34 PM"])
    status: Literal["success", "uploaded", "pending", "completed"]


class CoachSyncActivityResponse(BaseModel):
    """Sync activity list for the Sync Activity screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Sync activity loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000002",
                "title": "All Synced",
                "recent_activities": [
                    {
                        "title": "Practice Session synced successfully",
                        "time": "2:34 PM",
                        "status": "success",
                    }
                ],
                "save_status": "success",
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
    id: UUID = Field(description="Authenticated coach user identifier")
    title: str = Field(description="Status card title for the Sync Activity screen")
    recent_activities: list[SyncActivityItem] = Field(default_factory=list)
    save_status: str = Field(default="success")
    phone: str | None = None


class CoachSyncActivitySaveRequest(BaseModel):
    """Payload for POST /coach/sync-activity/save."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recent_activities": [
                    {
                        "title": "Practice Session synced successfully",
                        "time": "2:34 PM",
                        "status": "success",
                    }
                ],
                "phone": "+1-555-0100",
            }
        }
    )

    recent_activities: list[SyncActivityItem] = Field(
        default_factory=list,
        description="Recent sync activity rows to persist",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachSyncActivitySaveResponse(BaseModel):
    """Response after saving sync activity updates."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Sync activity saved successfully",
                "status": "saved",
                "description": "All recordings are up to date",
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000002",
                "title": "All Synced",
                "save_status": "success",
                "recent_activities": [
                    {
                        "title": "Practice Session synced successfully",
                        "time": "2:34 PM",
                        "status": "success",
                    }
                ],
                "phone": "+1-555-0100",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="saved")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Authenticated coach user identifier")
    title: str = Field(description="Status card title for the Sync Activity screen")
    save_status: str = Field(default="success")
    recent_activities: list[SyncActivityItem] = Field(default_factory=list)
    phone: str | None = None
