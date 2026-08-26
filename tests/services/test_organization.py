from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.services.organization import (
    build_pagination_meta,
    to_item,
    validate_address,
    validate_name,
    validate_phone_number,
)


def test_to_item_maps_admin_email_to_contact_email() -> None:
    org = Organization(
        id=uuid4(),
        name="Hoops Academy",
        admin_email="contact@example.com",
        phone_number="1234567890",
        address="123 Main St",
        join_code="ABCD1234",
        created_at=datetime.now(timezone.utc),
    )
    item = to_item(org)
    assert item.name == "Hoops Academy"
    assert item.organization == "Hoops Academy"
    assert item.contact_email == "contact@example.com"
    assert item.email == "contact@example.com"
    assert item.phone_number == "1234567890"
    assert item.phone == "1234567890"
    assert item.address == "123 Main St"
    assert item.description is None


def test_validate_phone_number_accepts_digits() -> None:
    assert validate_phone_number("1234567890") == "1234567890"


def test_validate_phone_number_rejects_invalid() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_phone_number("abc")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_name_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_name("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_address_strips() -> None:
    assert validate_address("  123 Main St  ") == "123 Main St"


def test_build_pagination_meta_empty() -> None:
    meta = build_pagination_meta(total=0, page=1, page_size=20)
    assert meta["total"] == 0
    assert meta["total_pages"] == 0
    assert meta["has_next"] is False
    assert meta["has_prev"] is False
