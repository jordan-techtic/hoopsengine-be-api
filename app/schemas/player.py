"""Pydantic schemas for coach player detail APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PLAYER_CREATE_EXAMPLE = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "1234567890",
    "gender": "Male",
    "date_of_birth": "2000-01-01",
    "team_selection": "Team A",
    "phone": "+1-555-0100",
}

PLAYER_CREATE_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Player added successfully",
    "status": "created",
    "description": "The player was added to your roster",
    "title": "Add Player",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "player_id": "11111111-2222-3333-4444-555555555555",
    "name": "John Doe",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "1234567890",
    "phone": "1234567890",
    "gender": "Male",
    "date_of_birth": "2000-01-01",
    "team_selection": "Team A",
    "team": "Team A",
}

PLAYER_LIST_EXAMPLE = {
    "success": True,
    "message": "Players loaded successfully",
    "status": "ready",
    "description": "Active players in your organization",
    "title": "My Players",
    "link": None,
    "error": None,
    "players": [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Jane Doe",
            "code": "PC-JANEDOE1",
            "player_code": "PC-JANEDOE1",
            "team_name": "Varsity Squad",
        }
    ],
}

PLAYER_SEARCH_EXAMPLE = {
    **PLAYER_LIST_EXAMPLE,
    "message": "Search results loaded successfully",
    "description": "Players matching your search query",
    "search_query": "Jane",
    "full_name": "Jane Doe",
}

PLAYER_DETAIL_EXAMPLE = {
    "success": True,
    "message": "Player details loaded successfully",
    "status": "ready",
    "description": "Player profile, statistics, and contact information",
    "title": "Player Details",
    "link": None,
    "error": None,
    "image": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "player_id": "11111111-2222-3333-4444-555555555555",
    "name": "Ava Morales",
    "email": "ava.morales@varsityacademy.com",
    "phone_number": "+1 (555) 382-9102",
    "phone": "+1-555-0100",
    "games_played": 12,
    "goals": 24,
    "assists": 0,
    "yellow_cards": 0,
    "makes": 24,
    "attempts": 48,
    "shooting_percent": 50,
    "position": "Forward",
    "role": None,
    "team": "Varsity Squad",
    "player_code": "PC-AVA001",
    "jersey_number": "23",
}


class PlayerCreateRequest(BaseModel):
    """Payload for POST /players."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_CREATE_EXAMPLE})

    first_name: str = Field(
        description="Player first name",
        examples=["John"],
    )
    last_name: str = Field(
        description="Player last name",
        examples=["Doe"],
    )
    email: str = Field(
        description="Player contact email",
        examples=["john.doe@example.com"],
    )
    phone_number: str = Field(
        description="Contact phone number stored on the player record",
        examples=["1234567890"],
    )
    gender: str = Field(
        description="Player gender label",
        examples=["Male"],
    )
    date_of_birth: str = Field(
        description="Player date of birth (YYYY-MM-DD or MM/DD/YYYY)",
        examples=["2000-01-01"],
    )
    team_selection: str = Field(
        description="Selected team name within the coach organization",
        examples=["Team A"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerCreateResponse(BaseModel):
    """Successful player creation response for the Add Player screen."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_CREATE_RESPONSE_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="created")
    description: str | None = None
    title: str = Field(default="Add Player")
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Created player UUID")
    player_id: UUID = Field(description="Same as id — bound for mobile navigation")
    name: str = Field(description="Full display name")
    first_name: str
    last_name: str
    email: str
    phone_number: str | None = None
    phone: str | None = Field(
        default=None,
        description="Echo of stored phone; mirrors phone_number",
    )
    gender: str | None = None
    date_of_birth: str | None = None
    team_selection: str | None = None
    team: str | None = Field(default=None, description="Resolved team display name")


class PlayerListItem(BaseModel):
    """Summary row for the My Players list and search results."""

    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Full display name")
    code: str | None = Field(default=None, description="Player code alias for mobile cards")
    player_code: str | None = Field(default=None, description="Unique player code")
    team_name: str | None = Field(default=None, description="Associated team display name")


class PlayerListResponse(BaseModel):
    """Response for GET /players (My Players list)."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_LIST_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="My Players")
    link: str | None = None
    error: None = None
    players: list[PlayerListItem] = Field(default_factory=list)


class PlayerSearchResponse(BaseModel):
    """Response for GET /players/search."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_SEARCH_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="My Players")
    link: str | None = None
    error: None = None
    search_query: str = Field(description="Normalized search text used for filtering")
    full_name: str | None = Field(
        default=None,
        description="Echo of the Figma player-name search input when provided",
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
    )
    players: list[PlayerListItem] = Field(default_factory=list)


class PlayerUpdateRequest(BaseModel):
    """Payload for PUT /players/{player_id}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Ava",
                "last_name": "Morales",
                "email": "ava.morales@varsityacademy.com",
                "phone_number": "+1 (555) 382-9102",
                "position": "Forward",
                "phone": "+1-555-0100",
            }
        }
    )

    first_name: str | None = Field(
        default=None,
        description="Player first name",
        examples=["Ava"],
    )
    last_name: str | None = Field(
        default=None,
        description="Player last name",
        examples=["Morales"],
    )
    email: str | None = Field(
        default=None,
        description="Player contact email",
        examples=["ava.morales@varsityacademy.com"],
    )
    phone_number: str | None = Field(
        default=None,
        description="Contact phone number stored on the player record",
        examples=["+1 (555) 382-9102"],
    )
    position: str | None = Field(
        default=None,
        description="Player position label",
        examples=["Forward"],
    )
    phone: str | None = Field(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    )


class PlayerDetailResponse(BaseModel):
    """Player detail response for the Player Details screen."""

    model_config = ConfigDict(json_schema_extra={"example": PLAYER_DETAIL_EXAMPLE})

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="Player Details")
    link: str | None = None
    error: None = None
    image: str | None = Field(
        default=None,
        description="Optional hero banner image URL when available",
    )
    id: UUID = Field(description="Player UUID")
    player_id: UUID = Field(description="Same as id — bound for mobile detail screens")
    name: str = Field(description="Full display name")
    email: str | None = Field(default=None, description="Contact email")
    phone_number: str | None = Field(default=None, description="Stored contact phone")
    phone: str | None = Field(
        default=None,
        description="Echo of client metadata; mirrors phone_number when stored",
    )
    games_played: int = Field(default=0, description="Distinct sessions with recorded stats")
    goals: int = Field(default=0, description="Total makes mapped for the statistics cards")
    assists: int = Field(default=0, description="Assists (not tracked — returns 0)")
    yellow_cards: int = Field(default=0, description="Discipline count (not tracked — returns 0)")
    makes: int = Field(default=0, description="Total makes from session data")
    attempts: int = Field(default=0, description="Total attempts from session data")
    shooting_percent: int = Field(default=0, description="Integer shooting percentage")
    position: str | None = Field(default=None, description="Player position")
    role: str | None = Field(
        default=None,
        description="Team role label when stored (e.g. Co-Captain)",
    )
    team: str | None = Field(default=None, description="Team display name")
    player_code: str | None = Field(default=None, description="Unique player code")
    jersey_number: str | None = Field(default=None, description="Jersey number when assigned")


class PlayerDeleteResponse(BaseModel):
    """Successful player removal response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Player removed successfully",
                "status": "ready",
                "description": "The player was removed from the roster",
                "title": "Player Details",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "player_id": "11111111-2222-3333-4444-555555555555",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(default="ready")
    description: str | None = None
    title: str = Field(default="Player Details")
    link: str | None = None
    error: None = None
    id: UUID
    player_id: UUID
