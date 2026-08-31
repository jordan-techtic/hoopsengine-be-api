"""Pydantic schemas for organization admin practice plan assignment APIs."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin
from app.schemas.practice_plan import PracticePlanDrillInput, PracticePlanItem

PRACTICE_PLAN_ASSIGN_EXAMPLE = {
    "coach_id": "22222222-3333-4444-5555-666666666666",
    "team_id": "33333333-4444-5555-6666-777777777777",
    "plan_id": "11111111-2222-3333-4444-555555555555",
    "start_date": "2026-09-01",
    "frequency": "Every Tuesday & Thursday",
    "phone": "+1-555-0100",
}

PRACTICE_PLAN_ASSIGNMENT_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Practice plan assigned successfully",
    "status": "assigned",
    "description": "Weekly shooting progression for varsity players",
    "link": None,
    "error": None,
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "title": "Shooting Fundamentals",
    "name": "Shooting Fundamentals",
    "image": None,
    "organization": "Courtside Elite Academy",
    "plan_id": "11111111-2222-3333-4444-555555555555",
    "coach_id": "22222222-3333-4444-5555-666666666666",
    "coach_name": "Coach Taylor",
    "team_id": "33333333-4444-5555-6666-777777777777",
    "team_name": "Varsity Boys",
    "start_date": "2026-09-01",
    "frequency": "Every Tuesday & Thursday",
    "drill_count": 8,
}


class PracticePlanAssignRequest(BaseModel):
    """Payload for POST /practice-plans/assign."""

    model_config = ConfigDict(json_schema_extra={"example": PRACTICE_PLAN_ASSIGN_EXAMPLE})

    coach_id: UUID | None = Field(
        default=None,
        description="Coach UUID receiving the practice plan assignment",
        examples=["22222222-3333-4444-5555-666666666666"],
    )
    team_id: UUID | None = Field(
        default=None,
        description="Optional team UUID the plan is assigned through",
        examples=["33333333-4444-5555-6666-777777777777"],
    )
    plan_id: UUID | None = Field(
        default=None,
        description="Practice plan UUID to assign",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    start_date: date | None = Field(
        default=None,
        description="Assignment start date (YYYY-MM-DD)",
        examples=["2026-09-01"],
    )
    frequency: str | None = Field(
        default=None,
        description="Human-readable practice frequency label",
        examples=["Every Tuesday & Thursday"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )

    @field_validator("frequency")
    @classmethod
    def strip_frequency(cls, value: str | None) -> str | None:
        """Normalize optional frequency text."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PracticePlanAssignmentUpdateRequest(BaseModel):
    """Payload for PUT /practice-plans/{id} when called by an organization admin."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "coach_id": "22222222-3333-4444-5555-666666666666",
                "team_id": "33333333-4444-5555-6666-777777777777",
                "plan_id": "11111111-2222-3333-4444-555555555555",
                "start_date": "2026-09-15",
                "frequency": "Every Monday & Wednesday",
                "phone": "+1-555-0100",
            }
        }
    )

    coach_id: UUID | None = Field(default=None, description="Updated coach UUID")
    team_id: UUID | None = Field(default=None, description="Updated team UUID")
    plan_id: UUID | None = Field(default=None, description="Updated practice plan UUID")
    start_date: date | None = Field(default=None, description="Updated assignment start date")
    frequency: str | None = Field(default=None, description="Updated frequency label")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )

    @field_validator("frequency")
    @classmethod
    def strip_frequency(cls, value: str | None) -> str | None:
        """Normalize optional frequency text."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class PracticePlanAssignmentItem(BaseModel):
    """Assigned practice plan summary for org-admin list responses."""

    id: UUID = Field(description="Assignment UUID")
    plan_id: UUID = Field(description="Practice plan UUID")
    title: str = Field(description="Plan title for hero cards")
    name: str = Field(description="Plan display name")
    description: str | None = Field(default=None, description="Plan description text")
    image: str | None = Field(default=None, description="Optional plan preview image URL")
    status: str = Field(default="assigned", description="Assignment lifecycle status")
    drill_count: int = Field(description="Number of drills in the assigned plan")
    coach_id: UUID = Field(description="Assigned coach UUID")
    coach_name: str = Field(description="Assigned coach display name")
    team_id: UUID | None = Field(default=None, description="Assigned team UUID")
    team_name: str | None = Field(default=None, description="Assigned team display name")
    start_date: date = Field(description="Assignment start date")
    frequency: str | None = Field(default=None, description="Practice frequency label")
    organization: str = Field(description="Organization display name")
    created_at: datetime | None = None


class PracticePlanAssignmentResponse(MobileWriteOnlyPasswordMixin):
    """Single practice plan assignment mutation response."""

    model_config = ConfigDict(
        json_schema_extra={"example": PRACTICE_PLAN_ASSIGNMENT_RESPONSE_EXAMPLE}
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="assigned")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Assignment UUID")
    title: str
    name: str
    image: str | None = None
    organization: str
    plan_id: UUID
    coach_id: UUID
    coach_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    start_date: date
    frequency: str | None = None
    drill_count: int = Field(default=0)


class PracticePlanAssignmentListResponse(MobileWriteOnlyPasswordMixin):
    """Available plans and assigned practice plans for org-admin assignment screens."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Practice plans loaded successfully",
                "status": "ready",
                "description": "Assign practice plans to coaches and teams",
                "link": None,
                "error": None,
                "organization": "Courtside Elite Academy",
                "plans": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Shooting Fundamentals",
                        "status": "active",
                        "drill_count": 8,
                        "duration": "80 min",
                        "category": "Skills",
                        "created_by_name": "Org Admin",
                        "drills": [],
                    }
                ],
                "assignments": [
                    {
                        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "plan_id": "11111111-2222-3333-4444-555555555555",
                        "title": "Shooting Fundamentals",
                        "name": "Shooting Fundamentals",
                        "description": "Weekly shooting progression",
                        "image": None,
                        "status": "assigned",
                        "drill_count": 8,
                        "coach_id": "22222222-3333-4444-5555-666666666666",
                        "coach_name": "Coach Taylor",
                        "team_id": "33333333-4444-5555-6666-777777777777",
                        "team_name": "Varsity Boys",
                        "start_date": "2026-09-01",
                        "frequency": "Every Tuesday & Thursday",
                        "organization": "Courtside Elite Academy",
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
    organization: str
    plans: list[PracticePlanItem] = Field(
        default_factory=list,
        description="Active practice plans available for assignment",
    )
    assignments: list[PracticePlanAssignmentItem] = Field(
        default_factory=list,
        description="Practice plans already assigned within the organization",
    )


class PracticePlanPutRequest(BaseModel):
    """Combined payload for PUT /practice-plans/{id}.

    Organization admins update assignment fields. Coaches update plan name and drills.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "start_date": "2026-09-15",
                    "frequency": "Every Monday & Wednesday",
                    "phone": "+1-555-0100",
                },
                {
                    "name": "Updated Warmup Plan",
                    "drills": [
                        {
                            "id": "11111111-2222-3333-4444-555555555555",
                            "name": "Free Throw Line",
                            "type": "free_throw",
                        }
                    ],
                    "phone": "+1-555-0100",
                },
            ]
        }
    )

    name: str | None = Field(default=None, description="Updated practice plan name (coach)")
    drills: list[PracticePlanDrillInput] | None = Field(
        default=None,
        description="Replacement drill list for the plan (coach)",
        min_length=1,
    )
    coach_id: UUID | None = Field(default=None, description="Updated coach UUID (org admin)")
    team_id: UUID | None = Field(default=None, description="Updated team UUID (org admin)")
    plan_id: UUID | None = Field(default=None, description="Updated practice plan UUID (org admin)")
    start_date: date | None = Field(default=None, description="Updated assignment start date (org admin)")
    frequency: str | None = Field(default=None, description="Updated frequency label (org admin)")
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )

    @field_validator("frequency")
    @classmethod
    def strip_frequency(cls, value: str | None) -> str | None:
        """Normalize optional frequency text."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
