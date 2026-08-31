"""Shared mobile client envelope fields for Coach module API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MobileEnvelopeMixin(BaseModel):
    """Base success/error envelope shared by mobile client API responses."""

    success: bool = Field(default=True, description="True on successful responses")
    error: dict[str, Any] | None = Field(
        default=None,
        description="Error object on failure responses; null on success",
    )


class MobileWriteOnlyPasswordMixin(MobileEnvelopeMixin):
    """Ensures read responses include a null password field for frontend form state."""

    password: None = Field(
        default=None,
        description="Always null on read responses (password is write-only)",
    )
