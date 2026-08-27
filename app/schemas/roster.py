"""Pydantic schemas for team roster search on the Practice Plans screen."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class PlayerRosterItem(BaseModel):
    """One player returned from roster search."""

    id: UUID = Field(description="Player UUID")
    name: str = Field(description="Full display name", examples=["Jane Hudson"])
    first_name: str = Field(description="Player first name", examples=["Jane"])
    last_name: str = Field(description="Player last name", examples=["Hudson"])
    jersey_number: str | None = Field(
        default=None,
        description="Jersey number when assigned",
        examples=["23"],
    )


class PlayerRosterSearchResponse(MobileWriteOnlyPasswordMixin):
    """Filtered team roster results for the Practice Plans player search input."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Players found",
                "status": "ready",
                "description": "Matching team roster players",
                "link": None,
                "error": None,
                "players": [
                    {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "name": "Jane Hudson",
                        "first_name": "Jane",
                        "last_name": "Hudson",
                        "jersey_number": "23",
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
    players: list[PlayerRosterItem] = Field(default_factory=list)
