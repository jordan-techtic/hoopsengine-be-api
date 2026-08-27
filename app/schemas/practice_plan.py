"""Pydantic schemas for coach practice plan CRUD APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PRACTICE_PLAN_WRITE_EXAMPLE = {
    "name": "Shooting Fundamentals",
    "drills": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Spot Up",
            "type": "shooting",
        }
    ],
    "phone": "+1-555-0100",
}


class PracticePlanDrillInput(BaseModel):
    """One drill entry within a practice plan write request."""

    id: UUID = Field(description="Drill UUID", examples=["11111111-2222-3333-4444-555555555555"])
    name: str = Field(description="Drill display name", examples=["Spot Up"])
    type: str = Field(description="Drill category or type label", examples=["shooting"])

    @field_validator("name", "type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Normalize drill text fields."""
        return value.strip()


class PracticePlanCreateRequest(BaseModel):
    """Payload for POST /practice-plans."""

    model_config = ConfigDict(json_schema_extra={"example": PRACTICE_PLAN_WRITE_EXAMPLE})

    name: str = Field(description="Practice plan name shown on the plan card", examples=["Shooting Fundamentals"])
    drills: list[PracticePlanDrillInput] = Field(
        description="Ordered list of drills included in the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PracticePlanUpdateRequest(BaseModel):
    """Payload for PUT /practice-plans/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Warmup Plan",
                "drills": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Free Throw Line",
                        "type": "free_throw",
                    }
                ],
                "phone": "+1-555-0100",
            }
        }
    )

    name: str | None = Field(default=None, description="Updated practice plan name")
    drills: list[PracticePlanDrillInput] | None = Field(
        default=None,
        description="Replacement drill list for the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PracticePlanDrillItem(BaseModel):
    """One drill returned with a practice plan."""

    id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Spot Up"])
    type: str = Field(description="Drill category or type", examples=["shooting"])


class PracticePlanItem(BaseModel):
    """Practice plan summary for list and detail responses."""

    id: UUID = Field(description="Practice plan UUID")
    name: str = Field(description="Plan name", examples=["Shooting Fundamentals"])
    drill_count: int = Field(description="Number of drills in the plan", examples=[3])
    created_by_name: str = Field(description="Coach name who created the plan", examples=["Regular Coach"])
    drills: list[PracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = Field(default=None, description="Plan creation timestamp")


class PracticePlanResponse(BaseModel):
    """Single practice plan mutation response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Practice plan created successfully",
                "status": "active",
                "description": "Your active practice plan is ready to use",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "Shooting Fundamentals",
                "drill_count": 1,
                "created_by_name": "Regular Coach",
                "drills": [
                    {
                        "id": "22222222-3333-4444-5555-666666666666",
                        "name": "Spot Up",
                        "type": "shooting",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="active", description="Plan lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    name: str
    drill_count: int
    created_by_name: str
    drills: list[PracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = None


class PracticePlanListResponse(BaseModel):
    """Active practice plans for the authenticated coach."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Active practice plans loaded successfully",
                "status": "ready",
                "description": "Your active practice plans",
                "link": None,
                "error": None,
                "plans": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Shooting Fundamentals",
                        "drill_count": 3,
                        "created_by_name": "Regular Coach",
                        "drills": [],
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
    plans: list[PracticePlanItem] = Field(default_factory=list)
