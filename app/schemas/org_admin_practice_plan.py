"""Pydantic schemas for organization admin practice plan CRUD APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

ORG_ADMIN_PRACTICE_PLAN_CREATE_EXAMPLE = {
    "name": "Shooting Fundamentals",
    "description": "Weekly shooting progression for varsity players",
    "drills": [
        {
            "drill_name": "Spot Up",
            "drill_description": "Catch-and-shoot from the wing",
        }
    ],
    "phone": "+1-555-0100",
}

ORG_ADMIN_PRACTICE_PLAN_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Practice plan created successfully",
    "status": "active",
    "description": "Weekly shooting progression for varsity players",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "title": "Shooting Fundamentals",
    "name": "Shooting Fundamentals",
    "organization": "Courtside Elite Academy",
    "drill_count": 1,
    "created_by_name": "Org Admin",
    "drills": [
        {
            "drill_name": "Spot Up",
            "drill_description": "Catch-and-shoot from the wing",
        }
    ],
}


class OrgAdminPracticePlanDrillInput(BaseModel):
    """One drill entry within an org-admin practice plan write request."""

    drill_name: str = Field(
        description="Drill display name",
        examples=["Spot Up"],
    )
    drill_description: str | None = Field(
        default=None,
        description="Optional drill description text",
        examples=["Catch-and-shoot from the wing"],
    )

    @field_validator("drill_name")
    @classmethod
    def strip_drill_name(cls, value: str) -> str:
        """Normalize drill name text."""
        return value.strip()


class OrgAdminPracticePlanDrillItem(BaseModel):
    """One drill returned with an org-admin practice plan."""

    drill_name: str = Field(description="Drill display name", examples=["Spot Up"])
    drill_description: str | None = Field(
        default=None,
        description="Drill description text",
        examples=["Catch-and-shoot from the wing"],
    )


class OrgAdminPracticePlanCreateRequest(BaseModel):
    """Payload for POST /admin/practice-plans."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_PRACTICE_PLAN_CREATE_EXAMPLE}
    )

    name: str = Field(
        description="Practice plan name",
        examples=["Shooting Fundamentals"],
    )
    description: str | None = Field(
        default=None,
        description="Practice plan description shown on plan detail cards",
        examples=["Weekly shooting progression for varsity players"],
    )
    drills: list[OrgAdminPracticePlanDrillInput] = Field(
        description="Ordered list of drills in the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Normalize plan name text."""
        return value.strip()


class OrgAdminPracticePlanUpdateRequest(BaseModel):
    """Payload for PUT /admin/practice-plans/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Warmup Plan",
                "description": "Revised pre-game warmup sequence",
                "drills": [
                    {
                        "drill_name": "Free Throw Line",
                        "drill_description": "Form shooting at the line",
                    }
                ],
                "phone": "+1-555-0100",
            }
        }
    )

    name: str | None = Field(default=None, description="Updated practice plan name")
    description: str | None = Field(
        default=None,
        description="Updated practice plan description",
    )
    drills: list[OrgAdminPracticePlanDrillInput] | None = Field(
        default=None,
        description="Replacement drill list for the plan",
        min_length=1,
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class OrgAdminPracticePlanItem(BaseModel):
    """Practice plan summary for org-admin list responses."""

    id: UUID = Field(description="Practice plan UUID")
    name: str = Field(description="Plan name", examples=["Warm-Up Routine"])
    title: str = Field(description="Plan title for mobile hero cards", examples=["Warm-Up Routine"])
    description: str | None = Field(
        default=None,
        description="Practice plan description text",
    )
    status: str = Field(default="active", description="Plan lifecycle status", examples=["active"])
    drill_count: int = Field(description="Number of drills in the plan", examples=[3])
    duration: str = Field(description="Estimated plan duration for list cards", examples=["30 min"])
    category: str = Field(description="Category tab label derived from drills", examples=["Skills"])
    created_by_name: str = Field(
        description="Coach or admin name who created the plan",
        examples=["Regular Coach"],
    )
    organization: str = Field(description="Organization display name", examples=["Courtside Elite Academy"])
    drills: list[OrgAdminPracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = Field(default=None, description="Plan creation timestamp")


class OrgAdminPracticePlanResponse(MobileWriteOnlyPasswordMixin):
    """Single org-admin practice plan mutation or detail response."""

    model_config = ConfigDict(json_schema_extra={"example": ORG_ADMIN_PRACTICE_PLAN_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="active", description="Plan lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    title: str = Field(description="Plan title for mobile hero cards")
    name: str
    organization: str = Field(description="Organization display name")
    drill_count: int
    created_by_name: str
    drills: list[OrgAdminPracticePlanDrillItem] = Field(default_factory=list)
    created_at: datetime | None = None


class OrgAdminPracticePlanListResponse(MobileWriteOnlyPasswordMixin):
    """Active practice plans for the authenticated organization admin."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Practice plans loaded successfully",
                "status": "ready",
                "description": "Your active practice plans",
                "link": None,
                "error": None,
                "organization": "Courtside Elite Academy",
                "plans": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Warm-Up Routine",
                        "title": "Warm-Up Routine",
                        "description": "Standard pre-practice warmup",
                        "status": "active",
                        "drill_count": 3,
                        "duration": "30 min",
                        "category": "Skills",
                        "created_by_name": "Regular Coach",
                        "organization": "Courtside Elite Academy",
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
    organization: str = Field(description="Organization display name")
    plans: list[OrgAdminPracticePlanItem] = Field(default_factory=list)
