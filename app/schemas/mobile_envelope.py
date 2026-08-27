"""Shared mobile client envelope fields for Coach module API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MobileWriteOnlyPasswordMixin(BaseModel):
    """Ensures read responses include a null password field for frontend form state."""

    password: None = Field(
        default=None,
        description="Always null on read responses (password is write-only)",
    )
