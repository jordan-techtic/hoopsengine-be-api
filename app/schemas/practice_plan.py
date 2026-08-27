"""Pydantic schemas for coach practice plan CRUD APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

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

CREATE_PRACTICE_PLAN_EXAMPLE = {
    "plan_name": "Morning Shooting Routine",
    "selected_drills": ["Spot Up", "Free Throw Line"],
    "full_name": "Jane Doe",
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
    """Payload for POST /practice-plans (Create and legacy coach formats)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [CREATE_PRACTICE_PLAN_EXAMPLE, PRACTICE_PLAN_WRITE_EXAMPLE]
        }
    )

    plan_name: str | None = Field(
        default=None,
        description="Practice plan name from the Create Practice Plan form",
        examples=["Morning Shooting Routine"],
    )
    full_name: str | None = Field(
        default=None,
        description="Figma alias for the plan name input (not the coach profile name)",
        examples=["Jane Doe"],
    )
    selected_drills: list[str] | None = Field(
        default=None,
        description="Ordered drill names selected from drill search results",
        examples=[["Spot Up", "Free Throw Line"]],
        min_length=1,
    )
    name: str | None = Field(
        default=None,
        description="Practice plan name (legacy alias)",
        examples=["Shooting Fundamentals"],
    )
    drills: list[PracticePlanDrillInput] | None = Field(
        default=None,
        description="Ordered list of drills with ids (legacy format)",
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
    name: str = Field(description="Plan name", examples=["Warm-Up Routine"])
    status: str = Field(default="active", description="Plan lifecycle status", examples=["active"])
    drill_count: int = Field(description="Number of drills in the plan", examples=[3])
    duration: str = Field(description="Estimated plan duration for list cards", examples=["30 min"])
    category: str = Field(
        description="Category tab label derived from drills",
        examples=["Skills"],
    )
    created_by_name: str = Field(description="Coach name who created the plan", examples=["Regular Coach"])
    drills: list[PracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = Field(default=None, description="Plan creation timestamp")


class PracticePlanResponse(MobileWriteOnlyPasswordMixin):
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
                "title": "Shooting Fundamentals",
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
    title: str = Field(description="Plan title for mobile hero cards", examples=["Shooting Fundamentals"])
    name: str
    drill_count: int
    created_by_name: str
    drills: list[PracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = None


class PracticePlanListResponse(MobileWriteOnlyPasswordMixin):
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
                        "name": "Warm-Up Routine",
                        "status": "active",
                        "drill_count": 3,
                        "duration": "30 min",
                        "category": "Skills",
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
