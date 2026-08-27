"""Pydantic schemas for coach home screen APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CoachHomeActivityItem(BaseModel):
    """Recent activity row for the coach home screen."""

    description: str
    timestamp: datetime


class CoachHomeAttendanceItem(BaseModel):
    """Attendance row for the coach home screen."""

    player_name: str
    status: str


class CoachHomeResponse(BaseModel):
    """Aggregated coach home screen payload."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Home screen loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000002",
                "name": "Regular Coach",
                "total_sessions": 100,
                "total_players": 20,
                "recent_activities": [
                    {
                        "description": "Practice recorded yesterday",
                        "timestamp": "2023-10-01T12:00:00Z",
                    }
                ],
                "attendance_records": [
                    {"player_name": "Alex Morgan", "status": "Present"}
                ],
                "phone": "+1-555-0100",
                "company": "Acme Realty",
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
    name: str = Field(description="Coach display name for the home header")
    total_sessions: int = Field(ge=0)
    total_players: int = Field(ge=0)
    recent_activities: list[CoachHomeActivityItem] = Field(default_factory=list)
    attendance_records: list[CoachHomeAttendanceItem] = Field(default_factory=list)
    phone: str | None = None
    company: str | None = None


class HomeActivityItem(BaseModel):
    """Activity item for GET /home/activities."""

    activity_id: UUID
    activity_text: str
    activity_date: datetime
    user_id: UUID


class HomeActivitiesResponse(BaseModel):
    """Paginated home activities response."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Authenticated coach user identifier")
    name: str = Field(description="Coach display name")
    activities: list[HomeActivityItem] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=10, description="Maximum activities per page")
    count: int = Field(ge=0, description="Number of activities returned in this page")


class HomeUserInfoResponse(BaseModel):
    """User info for GET /home/user-info."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Authenticated coach user identifier")
    name: str = Field(description="Coach display name")
    user_id: UUID
    organization_name: str
    welcome_message: str


class HomeNotificationItem(BaseModel):
    """Notification item for GET /home/notifications."""

    notification_id: UUID
    notification_text: str
    notification_date: datetime


class HomeNotificationsResponse(BaseModel):
    """Notifications list for GET /home/notifications."""

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Authenticated coach user identifier")
    name: str = Field(description="Coach display name")
    notifications: list[HomeNotificationItem] = Field(default_factory=list)
