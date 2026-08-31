"""Pydantic schemas for authenticated player My Progress APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class ProgressSessionHistoryItem(BaseModel):
    """One drill session row on the My Progress session history screen."""

    date: str = Field(description="Session date in ISO YYYY-MM-DD format", examples=["2026-08-04"])
    drill: str = Field(description="Drill display name", examples=["Catch & Shoot Wing Series"])
    attempts: int = Field(ge=0, examples=[30])
    makes: int = Field(ge=0, examples=[18])


class DrillPerformanceItem(BaseModel):
    """Aggregate performance metrics for one drill."""

    drill: str = Field(description="Drill display name", examples=["Catch & Shoot Wing Series"])
    attempts: int = Field(ge=0, examples=[55])
    makes: int = Field(ge=0, examples=[33])
    shooting_percentage: str = Field(description="Shooting percentage for the drill", examples=["60%"])


class MyProgressResponse(MobileWriteOnlyPasswordMixin):
    """Aggregate progress summary for the My Progress screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player progress loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000033",
                "name": "Jane Doe",
                "completed_sessions": 20,
                "total_attempts": 180,
                "makes": 110,
                "shooting_percentage": "61%",
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
    id: UUID = Field(description="Player roster identifier")
    name: str = Field(description="Player display name")
    completed_sessions: int = Field(ge=0)
    total_attempts: int = Field(ge=0)
    makes: int = Field(ge=0)
    shooting_percentage: str
    phone: str | None = None


class SessionHistoryResponse(MobileWriteOnlyPasswordMixin):
    """Session history list for the My Progress screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Session history loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000033",
                "name": "Jane Doe",
                "session_history": [
                    {
                        "date": "2026-08-06",
                        "drill": "Elbow Pull-Up Attack",
                        "attempts": 25,
                        "makes": 15,
                    }
                ],
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
    id: UUID
    name: str
    session_history: list[ProgressSessionHistoryItem] = Field(default_factory=list)
    phone: str | None = None


class DrillPerformanceResponse(MobileWriteOnlyPasswordMixin):
    """Per-drill performance metrics for the My Progress screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill performance loaded successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "00000000-0000-4000-8000-000000000033",
                "name": "Jane Doe",
                "drill_performance": [
                    {
                        "drill": "Catch & Shoot Wing Series",
                        "attempts": 30,
                        "makes": 18,
                        "shooting_percentage": "60%",
                    }
                ],
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
    id: UUID
    name: str
    drill_performance: list[DrillPerformanceItem] = Field(default_factory=list)
    phone: str | None = None
