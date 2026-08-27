"""Pydantic schemas for drill search APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class DrillSearchItem(BaseModel):
    """One drill returned from drill search."""

    id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    type: str = Field(description="Drill category", examples=["general"])


class DrillSearchResponse(MobileWriteOnlyPasswordMixin):
    """Drill search results for the Edit Practice Plan drill picker."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drills found",
                "status": "ready",
                "description": "Matching active drills",
                "link": None,
                "error": None,
                "drills": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Warm-up Lap",
                        "type": "general",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    drills: list[DrillSearchItem] = Field(default_factory=list)
