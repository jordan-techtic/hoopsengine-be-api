"""Pydantic schemas for coach sync queue APIs."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

QUEUE_ITEM_TYPES = ("practice_session", "session_data")
QUEUE_STATUSES = ("pending_sync", "synced", "failed")

COACH_QUEUE_UPDATE_EXAMPLE = {
    "item_id": "11111111-2222-3333-4444-555555555555",
    "item_type": "session_data",
    "status": "synced",
    "phone": "+1-555-0100",
}


class CoachQueueItem(BaseModel):
    """One item in the coach sync queue."""

    id: UUID = Field(description="Queue item identifier")
    title: str = Field(
        description="Display title for the queue row",
        examples=["Defense Drill Session - Jul 28"],
    )
    name: str = Field(description="Short item label", examples=["Defense Drill Session"])
    status: str = Field(description="Sync status", examples=["pending_sync"])
    item_type: str = Field(
        description="Underlying record type (`practice_session` or `session_data`)",
        examples=["session_data"],
    )


class CoachQueueListResponse(BaseModel):
    """Queue list for the Coach Queue screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Queue loaded successfully",
                "status": "ready",
                "description": "Will sync automatically when connected to an internet network.",
                "link": None,
                "error": None,
                "title": "3 Items Pending Sync",
                "name": "Jane Coach",
                "id": None,
                "pending_count": 3,
                "items": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "title": "Defense Drill Session - Jul 28",
                        "name": "Defense Drill Session",
                        "status": "pending_sync",
                        "item_type": "session_data",
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
    title: str = Field(description="Header text such as '3 Items Pending Sync'")
    name: str = Field(description="Authenticated coach display name")
    id: UUID | None = Field(default=None, description="Optional context identifier")
    pending_count: int = Field(description="Number of items pending synchronization", ge=0)
    items: list[CoachQueueItem] = Field(default_factory=list)


class CoachQueueUpdateRequest(BaseModel):
    """Payload for updating a queue item sync status."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_QUEUE_UPDATE_EXAMPLE})

    item_id: UUID = Field(
        ...,
        description="Queue item UUID to update",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    item_type: Literal["practice_session", "session_data"] = Field(
        ...,
        description="Record type (`practice_session` or `session_data`)",
        examples=["session_data"],
    )
    status: Literal["pending_sync", "synced", "failed"] = Field(
        ...,
        description="Updated sync status (`pending_sync`, `synced`, or `failed`)",
        examples=["synced"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachQueueUpdateResponse(BaseModel):
    """Response after updating a queue item."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Queue item updated successfully",
                "status": "synced",
                "description": "Item removed from the pending sync queue",
                "link": "/api/v1/coach/queue",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "Defense Drill Session - Jul 28",
                "name": "Defense Drill Session",
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
    title: str
    name: str
