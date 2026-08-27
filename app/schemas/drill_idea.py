"""Pydantic schemas for coach drill idea submission APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DRILL_IDEA_CREATE_EXAMPLE = {
    "drill_name": "3-on-2 Fast Break Transition",
    "category": "Shooting",
    "difficulty_level": "Intermediate",
    "instructions": "Outline the setup, rotation rules, and primary coaching cues.",
    "full_name": "3-on-2 Fast Break Transition",
    "phone": "+1-555-0100",
}


class DrillIdeaCreateRequest(BaseModel):
    """Payload for submitting a custom drill idea."""

    model_config = ConfigDict(json_schema_extra={"example": DRILL_IDEA_CREATE_EXAMPLE})

    drill_name: str | None = Field(
        default=None,
        description="Drill name (required unless full_name is provided)",
        examples=["3-on-2 Fast Break Transition"],
    )
    category: str = Field(
        ...,
        description="Drill category or focus area",
        examples=["Shooting"],
    )
    difficulty_level: str = Field(
        ...,
        description="Difficulty level (Beginner, Intermediate, or Advanced)",
        examples=["Intermediate"],
    )
    instructions: str = Field(
        ...,
        description="Detailed setup and coaching instructions",
        examples=["Outline the setup, rotation rules, and primary coaching cues."],
    )
    full_name: str | None = Field(
        default=None,
        description="Figma alias for the Drill Name field (used when drill_name is empty)",
        examples=["3-on-2 Fast Break Transition"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class DrillIdeaItem(BaseModel):
    """One submitted drill idea."""

    id: UUID = Field(description="Drill idea submission identifier")
    name: str = Field(description="Submitted drill name")
    category: str = Field(description="Drill category")
    difficulty_level: str = Field(description="Difficulty level")
    instructions: str = Field(description="Drill instructions")
    status: str = Field(description="Review status", examples=["pending"])


class DrillIdeaCreateResponse(BaseModel):
    """Response after submitting a drill idea."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill idea submitted successfully",
                "status": "submitted",
                "description": "Your drill idea has been sent for review",
                "link": "/api/v1/drill-ideas",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "3-on-2 Fast Break Transition",
                "category": "Shooting",
                "difficulty_level": "Intermediate",
                "instructions": "Outline the setup, rotation rules, and primary coaching cues.",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID
    name: str
    category: str
    difficulty_level: str
    instructions: str


class DrillIdeaListResponse(BaseModel):
    """List of submitted drill ideas for the authenticated coach."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill ideas loaded successfully",
                "status": "ready",
                "description": "Submitted custom drill ideas",
                "link": None,
                "error": None,
                "id": None,
                "drill_ideas": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "3-on-2 Fast Break Transition",
                        "category": "Shooting",
                        "difficulty_level": "Intermediate",
                        "instructions": "Outline the setup, rotation rules, and primary coaching cues.",
                        "status": "pending",
                    }
                ],
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID | None = Field(
        default=None,
        description="Optional identifier when a single drill idea context applies",
    )
    drill_ideas: list[DrillIdeaItem] = Field(default_factory=list)
