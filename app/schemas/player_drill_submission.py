"""Pydantic schemas for player drill submission APIs."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PLAYER_DRILL_SUBMISSION_CREATE_EXAMPLE = {
    "drill_name": "3-on-2 Fast Break Transition",
    "category": "Shooting",
    "difficulty_level": "Intermediate",
    "description": "Outline the setup, rotation rules, and primary coaching cues.",
    "full_name": "3-on-2 Fast Break Transition",
    "phone": "+1-555-0100",
}


class PlayerDrillSubmissionCreateRequest(BaseModel):
    """Payload for POST /api/v1/player/drill-submissions."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_DRILL_SUBMISSION_CREATE_EXAMPLE})

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
    description: str | None = Field(
        default=None,
        description="Description and instructions for the drill idea",
        examples=["Outline the setup, rotation rules, and primary coaching cues."],
    )
    instructions: str | None = Field(
        default=None,
        description="Optional alias for description",
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

    @model_validator(mode="after")
    def normalize_description(self) -> Self:
        if (self.description is None or not self.description.strip()) and self.instructions:
            object.__setattr__(self, "description", self.instructions)
        return self


class PlayerDrillSubmissionItem(BaseModel):
    """One player drill submission."""

    id: UUID = Field(description="Drill submission identifier")
    name: str = Field(description="Submitted drill name")
    category: str = Field(description="Drill category")
    difficulty_level: str = Field(description="Difficulty level")
    description: str = Field(description="Drill description and instructions")
    status: str = Field(description="Review status", examples=["pending"])


class PlayerDrillSubmissionCreateResponse(BaseModel):
    """Response after submitting a player drill idea."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill idea submitted successfully",
                "status": "submitted",
                "description": "Your drill idea has been sent for review",
                "link": "/api/v1/player/drill-submissions",
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "3-on-2 Fast Break Transition",
                "category": "Shooting",
                "difficulty_level": "Intermediate",
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


class PlayerDrillSubmissionListResponse(BaseModel):
    """List of drill submissions for the authenticated player."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill submissions loaded successfully",
                "status": "ready",
                "description": "Submitted custom drill ideas",
                "link": None,
                "error": None,
                "id": None,
                "drill_submissions": [],
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
        description="Optional identifier when a single drill submission context applies",
    )
    drill_submissions: list[PlayerDrillSubmissionItem] = Field(default_factory=list)


class PlayerDrillSubmissionDetailResponse(BaseModel):
    """Single drill submission detail for the authenticated player."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Drill submission loaded successfully",
                "status": "ready",
                "description": "Submitted custom drill idea",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "name": "3-on-2 Fast Break Transition",
                "category": "Shooting",
                "difficulty_level": "Intermediate",
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
