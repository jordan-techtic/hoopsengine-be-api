from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_super_admin, get_current_user
from app.api.routes.organizations import router as organizations_router
from app.core.database import get_db
from app.core.error_handlers import register_exception_handlers
from app.core.exceptions import AppException
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreateRequest

ORG_ID = uuid4()
ADMIN_USER = User(
    id=uuid4(),
    email="admin.hoopsengine@yopmail.com",
    encrypted_password="hashed",
    role="super_admin",
    is_super_admin=True,
    is_active=True,
)
COACH_USER = User(
    id=uuid4(),
    email="coach@example.com",
    encrypted_password="hashed",
    role="coach",
    is_super_admin=False,
    is_active=True,
)


def _build_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(organizations_router, prefix="/api/v1")
    return test_app


async def _override_db():
    yield AsyncMock()


@pytest.fixture
def app() -> FastAPI:
    test_app = _build_app()
    test_app.dependency_overrides[get_current_super_admin] = lambda: ADMIN_USER
    test_app.dependency_overrides[get_db] = _override_db
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _org() -> Organization:
    return Organization(
        id=ORG_ID,
        name="Organization Name",
        admin_email="contact@example.com",
        phone_number="1234567890",
        address="123 Main St",
        join_code="A1B2C3D4",
        created_at=datetime.now(timezone.utc),
    )


def test_create_organization_schema_example_fields() -> None:
    payload = OrganizationCreateRequest.model_validate(
        {
            "name": "Organization Name",
            "contact_email": "contact@example.com",
            "phone_number": "1234567890",
            "address": "123 Main St",
        }
    )
    assert payload.contact_email == "contact@example.com"


def test_list_organizations_200(client: TestClient) -> None:
    with patch(
        "app.api.routes.organizations.organization_service.list_organizations",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        response = client.get("/api/v1/super-admin/organizations")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 0


def test_create_organization_200(client: TestClient) -> None:
    with patch(
        "app.api.routes.organizations.organization_service.create_organization",
        new_callable=AsyncMock,
        return_value=_org(),
    ):
        response = client.post(
            "/api/v1/super-admin/organizations",
            json={
                "name": "Organization Name",
                "contact_email": "contact@example.com",
                "phone_number": "1234567890",
                "address": "123 Main St",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Organization Name"
    assert body["contact_email"] == "contact@example.com"
    assert body["email"] == "contact@example.com"
    assert body["phone_number"] == "1234567890"
    assert body["phone"] == "1234567890"
    assert body["address"] == "123 Main St"
    assert body["organization"] == "Organization Name"
    assert body["message"] == "Organization created successfully."


def test_create_organization_invalid_email_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/super-admin/organizations",
        json={
            "name": "Organization Name",
            "contact_email": "not-an-email",
            "phone_number": "1234567890",
            "address": "123 Main St",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] is not None


def test_create_organization_invalid_phone_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/super-admin/organizations",
        json={
            "name": "Organization Name",
            "contact_email": "contact@example.com",
            "phone_number": "abc",
            "address": "123 Main St",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]


def test_update_organization_200(client: TestClient) -> None:
    updated = _org()
    updated.name = "Updated Name"
    with patch(
        "app.api.routes.organizations.organization_service.update_organization",
        new_callable=AsyncMock,
        return_value=updated,
    ):
        response = client.put(
            f"/api/v1/super-admin/organizations/{ORG_ID}",
            json={"name": "Updated Name"},
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["message"] == "Organization updated successfully."


def test_delete_organization_200(client: TestClient) -> None:
    with patch(
        "app.api.routes.organizations.organization_service.delete_organization",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.delete(f"/api/v1/super-admin/organizations/{ORG_ID}")
    assert response.status_code == 200
    assert response.json()["message"] == "Organization removed successfully."


def test_update_organization_404(client: TestClient) -> None:
    with patch(
        "app.api.routes.organizations.organization_service.update_organization",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=404,
        ),
    ):
        response = client.put(
            f"/api/v1/super-admin/organizations/{ORG_ID}",
            json={"name": "Updated Name"},
        )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert body["error"]["message"] == "Organization not found"


def test_delete_organization_404(client: TestClient) -> None:
    with patch(
        "app.api.routes.organizations.organization_service.delete_organization",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=404,
        ),
    ):
        response = client.delete(f"/api/v1/super-admin/organizations/{ORG_ID}")
    assert response.status_code == 404


def test_organizations_forbidden_403() -> None:
    test_app = _build_app()
    test_app.dependency_overrides[get_current_user] = lambda: COACH_USER
    test_app.dependency_overrides[get_db] = _override_db
    with TestClient(test_app) as test_client:
        response = test_client.get("/api/v1/super-admin/organizations")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


def test_organizations_unauthorized_401() -> None:
    test_app = _build_app()
    with TestClient(test_app) as test_client:
        response = test_client.get("/api/v1/super-admin/organizations")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}
