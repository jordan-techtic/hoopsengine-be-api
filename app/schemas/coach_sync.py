"""Pydantic schemas for coach offline sync APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CoachSyncTriggerRequest(BaseModel):
    """Payload for POST /coach/sync."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "+1-555-0100",
            }
        }
    )

    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachClearCacheRequest(BaseModel):
    """Payload for POST /coach/clear-cache."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "+1-555-0100",
            }
        }
    )

    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachSyncPreferencesUpdateRequest(BaseModel):
    """Payload for PUT /coach/sync/preferences."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "auto_sync": True,
                "sync_frequency": "Every 15 minutes",
                "phone": "+1-555-0100",
            }
        }
    )

    auto_sync: bool | None = Field(default=None, description="Whether auto sync is enabled")
    sync_frequency: str | None = Field(
        default=None,
        description="Sync frequency label or numeric minutes",
        examples=["Every 15 minutes"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachSyncActionResponse(BaseModel):
    """Generic success response for sync actions."""

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Authenticated coach user identifier")


class CoachSyncPreferencesResponse(BaseModel):
    """Sync preferences for the Offline Sync screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Sync preferences loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000002",
                "auto_sync": True,
                "sync_frequency": "Every 15 minutes",
                "last_synced": "Today, 2:34 PM",
                "pending_uploads": 3,
                "local_storage_used": "2.4 GB / 8 GB",
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
    auto_sync: bool
    sync_frequency: str
    last_synced: str | None = None
    pending_uploads: int = Field(ge=0)
    local_storage_used: str | None = None
    phone: str | None = None
