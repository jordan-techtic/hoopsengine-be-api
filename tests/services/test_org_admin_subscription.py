"""Unit tests for organization admin subscription service helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services import org_admin_subscription as org_admin_subscription_service


def test_renewal_warning_within_five_days() -> None:
    now = datetime(2026, 2, 10, tzinfo=timezone.utc)
    expiry = datetime(2026, 2, 14, tzinfo=timezone.utc)
    warning = org_admin_subscription_service._renewal_warning(expiry, now=now)
    assert warning is not None
    assert "5 days" in warning


def test_renewal_warning_outside_window() -> None:
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    expiry = datetime(2026, 2, 20, tzinfo=timezone.utc)
    warning = org_admin_subscription_service._renewal_warning(expiry, now=now)
    assert warning is None


def test_renewal_date_iso() -> None:
    assert (
        org_admin_subscription_service._renewal_date_iso(
            datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)
        )
        == "2026-02-15"
    )
