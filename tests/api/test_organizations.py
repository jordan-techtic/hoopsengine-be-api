"""Integration tests for Super Admin Manage Organizations API (JAW-9602)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import ORG_BASE, SEEDED_ORG_ID, auth_headers, make_expired_token


def _org_payload(**overrides: object) -> dict[str, object]:
    """Ticket example organization body with optional field overrides."""
    payload: dict[str, object] = {
        "name": "Organization Name",
        "contact_email": "contact@example.com",
        "phone_number": "1234567890",
        "address": "123 Main St",
    }
    payload.update(overrides)
    return payload


def test_list_organizations_returns_200_with_items(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: View list of organizations and return 200 with organization data."""
    response = client.get(ORG_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "pagination" in body
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["total"] >= 1
    names = {item["name"] for item in body["items"]}
    assert "Seeded Hoops Club" in names
    seeded = next(item for item in body["items"] if item["id"] == str(SEEDED_ORG_ID))
    assert seeded["contact_email"] == "seeded-org@test.com"
    assert seeded["email"] == "seeded-org@test.com"
    assert seeded["phone_number"] == "5551234567"
    assert seeded["phone"] == "5551234567"
    assert seeded["organization"] == "Seeded Hoops Club"


def test_create_organization_returns_200_with_data(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Add a new organization and return 200 with organization data."""
    response = client.post(ORG_BASE, headers=admin_headers, json=_org_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Organization created successfully."
    assert body["name"] == "Organization Name"
    assert body["organization"] == "Organization Name"
    assert body["contact_email"] == "contact@example.com"
    assert body["email"] == "contact@example.com"
    assert body["phone_number"] == "1234567890"
    assert body["phone"] == "1234567890"
    assert body["address"] == "123 Main St"
    assert "id" in body
    assert body["join_code"]
    assert len(body["join_code"]) == 8


def test_update_organization_returns_200_with_data(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Edit an existing organization and return 200 with organization data."""
    response = client.put(
        f"{ORG_BASE}/{SEEDED_ORG_ID}",
        headers=admin_headers,
        json={"name": "Updated Name"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Organization updated successfully."
    assert body["name"] == "Updated Name"
    assert body["organization"] == "Updated Name"
    assert body["id"] == str(SEEDED_ORG_ID)
    assert body["contact_email"] == "seeded-org@test.com"


def test_delete_organization_returns_200(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Remove an organization."""
    created = client.post(
        ORG_BASE,
        headers=admin_headers,
        json=_org_payload(contact_email="delete-me@example.com"),
    )
    assert created.status_code == 200
    org_id = created.json()["id"]

    response = client.delete(f"{ORG_BASE}/{org_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Organization removed successfully."

    listed = client.get(ORG_BASE, headers=admin_headers)
    ids = {item["id"] for item in listed.json()["items"]}
    assert org_id not in ids


def test_create_organization_invalid_email_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Reject a syntactically invalid contact_email."""
    response = client.post(
        ORG_BASE,
        headers=admin_headers,
        json=_org_payload(contact_email="not-an-email"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] is not None


def test_create_organization_invalid_phone_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Return 400 status for invalid organization data (phone)."""
    response = client.post(
        ORG_BASE,
        headers=admin_headers,
        json=_org_payload(phone_number="abc"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]


def test_update_organization_not_found_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Return 404 status for organization not found on update."""
    missing_id = uuid4()
    response = client.put(
        f"{ORG_BASE}/{missing_id}",
        headers=admin_headers,
        json={"name": "Updated Name"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert body["error"]["message"] == "Organization not found"


def test_delete_organization_not_found_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9602: Return 404 status for organization not found on delete."""
    missing_id = uuid4()
    response = client.delete(f"{ORG_BASE}/{missing_id}", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


def test_list_organizations_missing_token_401(client: TestClient) -> None:
    """Missing Authorization header is rejected with 401."""
    response = client.get(ORG_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


def test_list_organizations_forbidden_for_regular_user_403(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    """A coach cannot list organizations."""
    response = client.get(ORG_BASE, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_list_organizations_forbidden_for_viewer_403(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    """A player/readonly user cannot list organizations."""
    response = client.get(ORG_BASE, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_organization_forbidden_for_regular_user_403(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    """A coach cannot create organizations."""
    response = client.post(ORG_BASE, headers=user_headers, json=_org_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_list_organizations_inactive_user_401(
    client: TestClient, inactive_headers: dict[str, str]
) -> None:
    """A deactivated account cannot call super-admin endpoints."""
    response = client.get(ORG_BASE, headers=inactive_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_list_organizations_expired_token_401(
    client: TestClient, seeded_users: dict
) -> None:
    """An expired access token is rejected with 401."""
    token = make_expired_token(seeded_users["admin"]["id"])
    response = client.get(ORG_BASE, headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_create_organization_empty_name_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Empty name fails request validation."""
    response = client.post(
        ORG_BASE, headers=admin_headers, json=_org_payload(name="")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_organization_whitespace_name_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Whitespace-only name is treated as empty."""
    response = client.post(
        ORG_BASE, headers=admin_headers, json=_org_payload(name="   ")
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_organization_name_too_long_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Name longer than 255 characters is rejected."""
    response = client.post(
        ORG_BASE, headers=admin_headers, json=_org_payload(name="x" * 256)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_organization_max_length_name_200(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """A 255-character name is accepted."""
    name = "N" * 255
    response = client.post(
        ORG_BASE,
        headers=admin_headers,
        json=_org_payload(name=name, contact_email="max-name@example.com"),
    )
    assert response.status_code == 200
    assert response.json()["name"] == name


def test_create_organization_unicode_and_special_chars_200(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Unicode names and formatted phone numbers are stored."""
    response = client.post(
        ORG_BASE,
        headers=admin_headers,
        json=_org_payload(
            name="Café Hoops バスケット",
            contact_email="unicode.org@example.com",
            phone_number="+1 (234) 567-8901",
            address="Calle 123, São Paulo",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Café Hoops バスケット"
    assert body["phone_number"] == "+1 (234) 567-8901"
    assert body["address"] == "Calle 123, São Paulo"


def test_create_organization_missing_fields_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Omitting required fields returns 422."""
    response = client.post(
        ORG_BASE, headers=admin_headers, json={"name": "Only Name"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_organization_empty_payload_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Updating with no fields returns 400."""
    response = client.put(
        f"{ORG_BASE}/{SEEDED_ORG_ID}", headers=admin_headers, json={}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_organization_invalid_id_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """A non-UUID path parameter is a validation error."""
    response = client.put(
        f"{ORG_BASE}/not-a-uuid",
        headers=admin_headers,
        json={"name": "Updated Name"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_organizations_page_out_of_range_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """page must be >= 1."""
    response = client.get(f"{ORG_BASE}?page=0", headers=admin_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_organizations_search_filters(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Optional search matches organization name."""
    response = client.get(
        f"{ORG_BASE}?search=Seeded", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    assert all("Seeded" in item["name"] for item in body["items"])
