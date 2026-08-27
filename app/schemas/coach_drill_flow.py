"""Pydantic schemas for One Drill Step-1 coach drill flow endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

COACH_DRILL_SEARCH_EXAMPLE = {
    "search_query": "Jane",
    "full_name": "Jane Hudson",
    "phone": "+1-555-0100",
}

COACH_DRILL_SELECT_EXAMPLE = {
    "selected_player_id": "00000000-0000-4000-8000-000000000033",
    "full_name": "Jane Hudson",
    "phone": "+1-555-0100",
}

COACH_DRILL_CONTINUE_EXAMPLE = {
    "phone": "+1-555-0100",
}


class CoachDrillPlayerItem(BaseModel):
    """Player row shown in One Drill Step-1 search results."""

    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Player full name", examples=["Jane Hudson"])
    code: str | None = Field(default=None, description="Player code", examples=["PC-JANE001"])
    player_code: str | None = Field(default=None, description="Alias of code")
    jersey_number: str | None = Field(default=None, description="Jersey number", examples=["23"])
    team_name: str | None = Field(default=None, description="Team name when available")


class CoachDrillSearchRequest(BaseModel):
    """Search players by name or jersey number on One Drill Step-1."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_DRILL_SEARCH_EXAMPLE})

    search_query: str | None = Field(
        default=None,
        description="Search term matched against player name or jersey number",
        examples=["Jane"],
    )
    full_name: str | None = Field(
        default=None,
        description="Figma alias for player name search input",
        examples=["Jane Hudson"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachDrillSearchResponse(BaseModel):
    """Player search results for One Drill Step-1."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Search results loaded successfully",
                "status": "ready",
                "description": "Players matching 'Jane'",
                "link": None,
                "error": None,
                "search_query": "Jane",
                "full_name": "Jane Hudson",
                "players": [
                    {
                        "id": "00000000-0000-4000-8000-000000000033",
                        "name": "Jane Hudson",
                        "code": "PC-JANE001",
                        "player_code": "PC-JANE001",
                        "jersey_number": "23",
                        "team_name": None,
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
    search_query: str
    full_name: str | None = None
    players: list[CoachDrillPlayerItem] = Field(default_factory=list)


class CoachDrillSelectPlayerRequest(BaseModel):
    """Select a player to begin the One Drill flow."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_DRILL_SELECT_EXAMPLE})

    selected_player_id: UUID = Field(
        ...,
        description="UUID of the player selected for the drill",
        examples=["00000000-0000-4000-8000-000000000033"],
    )
    full_name: str | None = Field(
        default=None,
        description="Optional Figma player name metadata (not persisted)",
        examples=["Jane Hudson"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachDrillSelectPlayerResponse(BaseModel):
    """Confirmation after selecting a player on One Drill Step-1."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player selected successfully",
                "status": "ready",
                "description": "Continue to select a drill",
                "link": "/api/v1/coach/drills/continue",
                "error": None,
                "selected_player_id": "00000000-0000-4000-8000-000000000033",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    selected_player_id: UUID


class CoachDrillContinueRequest(BaseModel):
    """Continue from One Drill Step-1 after player selection."""

    model_config = ConfigDict(json_schema_extra={"example": COACH_DRILL_CONTINUE_EXAMPLE})

    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class CoachDrillContinueResponse(BaseModel):
    """Response after advancing from Step-1 to Step-2."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Ready to select a drill",
                "status": "ready",
                "description": "Step 2: Select Drill",
                "link": "/coach/record/one-drill/step-2",
                "error": None,
                "step": 2,
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str
    description: str | None = None
    link: str | None = None
    error: None = None
    step: int = Field(description="Current step in the One Drill flow", examples=[2])
