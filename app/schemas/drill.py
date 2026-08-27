"""Pydantic schemas for drill catalog and One Drill Step-2 APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

DRILL_LIST_EXAMPLE = {
    "success": True,
    "message": "Drills loaded successfully",
    "status": "ready",
    "description": "Choose a drill to track performance metrics",
    "link": None,
    "error": None,
    "search": "warm",
    "full_name": None,
    "drills": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Warm-up Lap",
            "category": "general",
            "duration": 300,
            "image": None,
        }
    ],
}

DRILL_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Drill details loaded successfully",
    "status": "ready",
    "description": "Focus on a single drill and track reps, time, or performance",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "name": "Warm-up Lap",
    "category": "general",
    "duration": 300,
    "image": None,
}

DRILL_CREATE_EXAMPLE = {
    "drill_name": "3-Point Corner",
    "drill_category": "shooting",
    "duration": 60,
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}

DRILL_CONTINUE_EXAMPLE = {
    "selected_drill_id": "11111111-2222-3333-4444-555555555555",
    "full_name": "Jane Doe",
    "phone": "+1-555-0100",
}


class DrillSearchItem(BaseModel):
    """One drill returned from legacy drill search."""

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


class DrillListItem(BaseModel):
    """One drill in the One Drill Step-2 catalog list."""

    id: UUID = Field(description="Drill UUID")
    name: str = Field(description="Drill display name", examples=["Warm-up Lap"])
    category: str = Field(description="Drill category", examples=["shooting"])
    duration: int = Field(description="Drill duration in seconds", examples=[300], ge=0)
    image: str | None = Field(
        default=None,
        description="Optional drill thumbnail or diagram URL",
        examples=[None],
    )


class DrillListResponse(MobileWriteOnlyPasswordMixin):
    """Drill catalog list for the One Drill Step-2 screen."""

    model_config = ConfigDict(json_schema_extra={"example": DRILL_LIST_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = Field(
        default=None,
        description="Screen subtitle shown under the section header",
    )
    link: str | None = None
    error: None = None
    search: str | None = Field(
        default=None,
        description="Applied search term when filtering by name",
    )
    full_name: str | None = Field(
        default=None,
        description="Figma search input alias (`Search drills by name...`)",
    )
    drills: list[DrillListItem] = Field(default_factory=list)


class DrillDetailResponse(MobileWriteOnlyPasswordMixin):
    """Single drill detail for the One Drill Step-2 drill picker."""

    model_config = ConfigDict(json_schema_extra={"example": DRILL_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    name: str
    category: str
    duration: int = Field(ge=0)
    image: str | None = None


class DrillCreateRequest(BaseModel):
    """Payload for POST /drills."""

    model_config = ConfigDict(json_schema_extra={"example": DRILL_CREATE_EXAMPLE})

    drill_name: str = Field(description="Drill name (required)", examples=["3-Point Corner"])
    drill_category: str = Field(description="Drill category (required)", examples=["shooting"])
    duration: int | None = Field(
        default=None,
        description="Optional drill duration in seconds",
        examples=[60],
        ge=0,
    )
    full_name: str | None = Field(
        default=None,
        description="Figma drill name search alias (not persisted)",
        examples=["Jane Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class DrillUpdateRequest(BaseModel):
    """Payload for PUT /drills/{id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "drill_name": "3-Point Corner",
                "drill_category": "shooting",
                "duration": 90,
                "phone": "+1-555-0100",
            }
        }
    )

    drill_name: str | None = Field(default=None, description="Updated drill name")
    drill_category: str | None = Field(default=None, description="Updated drill category")
    duration: int | None = Field(default=None, description="Updated duration in seconds", ge=0)
    full_name: str | None = Field(default=None, description="Figma metadata (not persisted)")
    phone: str | None = Field(default=None, description="Client metadata (not persisted)")


class DrillMutationResponse(MobileWriteOnlyPasswordMixin):
    """Created or updated drill returned to the mobile client."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill created successfully",
                "status": "ready",
                "description": "Drill is available for selection",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "3-Point Corner",
                "category": "shooting",
                "duration": 60,
                "image": None,
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
    category: str
    duration: int = Field(ge=0)
    image: str | None = None


class DrillDeleteResponse(MobileWriteOnlyPasswordMixin):
    """Delete drill confirmation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill deleted successfully",
                "status": "ready",
                "description": None,
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
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


class DrillContinueRequest(BaseModel):
    """Payload for POST /drills/continue after selecting a drill."""

    model_config = ConfigDict(json_schema_extra={"example": DRILL_CONTINUE_EXAMPLE})

    selected_drill_id: UUID = Field(
        description="UUID of the drill selected on Step 2",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    full_name: str | None = Field(
        default=None,
        description="Figma search input metadata (not persisted)",
        examples=["Jane Doe"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class DrillContinueResponse(MobileWriteOnlyPasswordMixin):
    """Continue action response after drill selection."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill selected successfully",
                "status": "ready",
                "description": "Proceed to record session metrics",
                "link": "/coach/record/one-drill/step-3",
                "error": None,
                "selected_drill_id": "11111111-2222-3333-4444-555555555555",
                "step": 3,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    link: str | None = None
    error: None = None
    selected_drill_id: UUID
    step: int = Field(description="Next step in the One Drill flow", examples=[3])
