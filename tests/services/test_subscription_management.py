"""Unit tests for subscription management validation helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.user import User
from app.services.subscription_management import _format_expiry_date, _user_full_name


def test_format_expiry_date_matches_ticket_example() -> None:
    value = datetime(2026, 2, 15, tzinfo=timezone.utc)
    assert _format_expiry_date(value) == "Feb 15, 2026"


def test_user_full_name_uses_first_and_last_name() -> None:
    user = User(
        email="coach@test.com",
        encrypted_password="hashed",
        first_name="Jane",
        last_name="Doe",
    )
    assert _user_full_name(user) == "Jane Doe"


def test_user_full_name_falls_back_to_username() -> None:
    user = User(
        email="coach@test.com",
        encrypted_password="hashed",
        username="coachuser",
    )
    assert _user_full_name(user) == "coachuser"
