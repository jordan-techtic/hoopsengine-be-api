from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_super_admin, get_current_user
from app.api.routes.users import router as users_router
from app.core.database import get_db
from app.core.error_handlers import register_exception_handlers
from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import AdminUserCreateRequest

ADMIN_ID = uuid4()
USER_ID = uuid4()
ADMIN_USER = User(
    id=ADMIN_ID,
    email="admin.hoopsengine@yopmail.com",
    encrypted_password="hashed",
    role="super_admin",
    first_name="Super",
    last_name="Admin",
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
    test_app.include_router(users_router, prefix="/api/v1")
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


def _user() -> User:
    return User(
        id=USER_ID,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        encrypted_password="hashed",
        role=UserRole.COACH.value,
        is_super_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_create_schema_includes_ticket_fields() -> None:
    payload = AdminUserCreateRequest.model_validate(
        {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "Coach@123",
            "role": "coach",
        }
    )
    assert payload.email == "john.doe@example.com"
    assert payload.password == "Coach@123"


def test_list_users_200(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.list_users",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        response = client.get("/api/v1/super-admin/users")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 0
    assert body["roles"]
    assert {item["value"] for item in body["roles"]} >= {"coach", "player"}


def test_create_user_200_omits_password(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.create_user",
        new_callable=AsyncMock,
        return_value=_user(),
    ):
        response = client.post(
            "/api/v1/super-admin/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "password": "Coach@123",
                "role": "coach",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(USER_ID)
    assert body["email"] == "john.doe@example.com"
    assert body["role"] == "coach"
    assert body["name"] == "John Doe"
    assert body["roles"] == ["coach"]
    assert "password" not in body
    assert "encrypted_password" not in body
    assert body["message"] == "User created successfully."


def test_create_user_invalid_role_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/super-admin/users",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "Coach@123",
            "role": "not-a-role",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_weak_password_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/super-admin/users",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "password123",
            "role": "coach",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_duplicate_email_409(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.create_user",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
        ),
    ):
        response = client.post(
            "/api/v1/super-admin/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "password": "Coach@123",
                "role": "coach",
            },
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_update_user_404(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.update_user",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="USER_NOT_FOUND",
            message="User not found",
            status_code=404,
        ),
    ):
        response = client.put(
            f"/api/v1/super-admin/users/{USER_ID}",
            json={"first_name": "Jane"},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_delete_user_404(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.delete_user",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="USER_NOT_FOUND",
            message="User not found",
            status_code=404,
        ),
    ):
        response = client.delete(f"/api/v1/super-admin/users/{USER_ID}")
    assert response.status_code == 404


def test_delete_self_400(client: TestClient) -> None:
    with patch(
        "app.api.routes.users.user_service.delete_user",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="CANNOT_DELETE_SELF",
            message="You cannot remove your own account",
            status_code=400,
        ),
    ) as mocked:
        response = client.delete(f"/api/v1/super-admin/users/{ADMIN_ID}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_DELETE_SELF"
    mocked.assert_awaited()


def test_users_forbidden_403() -> None:
    test_app = _build_app()
    test_app.dependency_overrides[get_current_user] = lambda: COACH_USER
    test_app.dependency_overrides[get_db] = _override_db
    with TestClient(test_app) as test_client:
        response = test_client.get("/api/v1/super-admin/users")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_users_unauthorized_401() -> None:
    test_app = _build_app()
    with TestClient(test_app) as test_client:
        response = test_client.get("/api/v1/super-admin/users")
    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}
