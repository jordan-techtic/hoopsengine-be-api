"""Pydantic schemas for Edit Practice Plan coach endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

COACH_PRACTICE_PLAN_WRITE_EXAMPLE = {
    "title": "Shooting Fundamentals",
    "description": "Practice plan details here.",
    "drills": [
        {"name": "Warm-up Lap"},
        {"name": "Free Throw Set"},
        {"name": "3-Point Corner"},
        {"name": "Defensive Slides"},
    ],
    "phone": "+1-555-0100",
}


class CoachPracticePlanDrillInput(BaseModel):
    """One drill entry within an Edit Practice Plan write request."""

    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    id: UUID | None = Field(
        default=None,
        description="Optional drill UUID when known from drill search",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    type: str | None = Field(
        default=None,
        description="Optional drill category label",
        examples=["shooting"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Normalize drill name."""
        return value.strip()


class CoachPracticePlanDrillItem(BaseModel):
    """One drill returned with a practice plan detail response."""

    id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    type: str = Field(description="Drill category or type", examples=["general"])


class CoachPracticePlanCreateRequest(BaseModel):
    """Payload for POST /coach/practice-plans."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_PRACTICE_PLAN_WRITE_EXAMPLE})

    plan_name: str | None = Field(
        default=None,
        description="Practice plan name (alias accepted by mobile clients)",
        examples=["Shooting Fundamentals"],
    )
    title: str | None = Field(
        default=None,
        description="Practice plan title shown on the plan hero card",
        examples=["Shooting Fundamentals"],
    )
    name: str | None = Field(
        default=None,
        description="Practice plan name (legacy alias)",
        examples=["Shooting Fundamentals"],
    )
    description: str | None = Field(
        default=None,
        description="Plan details copy shown under the hero card title",
        examples=["Practice plan details here."],
    )
    drills: list[CoachPracticePlanDrillInput] = Field(
        description="Ordered list of drills included in the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachPracticePlanUpdateRequest(BaseModel):
    """Payload for PUT /coach/practice-plans/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_name": "Updated Warmup Plan",
                "description": "Updated plan details.",
                "drills": [{"name": "Free Throw Set"}],
                "phone": "+1-555-0100",
            }
        }
    )

    plan_name: str | None = Field(default=None, description="Updated practice plan name")
    title: str | None = Field(default=None, description="Updated practice plan title")
    name: str | None = Field(default=None, description="Updated practice plan name (legacy alias)")
    description: str | None = Field(
        default=None,
        description="Updated plan details copy for the hero card",
    )
    drills: list[CoachPracticePlanDrillInput] | None = Field(
        default=None,
        description="Replacement drill list for the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachPracticePlanResponse(MobileWriteOnlyPasswordMixin):
    """Single practice plan response for Edit Practice Plan screens."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Practice plan loaded successfully",
                "status": "active",
                "description": "Plan Details",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "Shooting Fundamentals",
                "name": "Shooting Fundamentals",
                "drill_count": 4,
                "created_by_name": "Regular Coach",
                "drills": [
                    {"id": "22222222-3333-4444-5555-666666666666", "name": "Warm-up Lap", "type": "general"},
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="active", description="Plan lifecycle status for the mobile client")
    description: str | None = Field(
        default=None,
        description="Plan details copy for the hero card",
        examples=["Plan Details"],
    )
    link: str | None = None
    error: None = None
    id: UUID
    title: str = Field(description="Plan title for the hero card", examples=["Shooting Fundamentals"])
    name: str = Field(description="Plan name", examples=["Shooting Fundamentals"])
    drill_count: int
    created_by_name: str
    drills: list[CoachPracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = None
