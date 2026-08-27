"""PostgreSQL test infrastructure for Super Admin organization, user, and dashboard APIs."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.test")

# Test-only credentials loaded from environment (.env.test) — never use production secrets.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/hoops_engine_test"),
)
TEST_SECRET_KEY = os.environ.get("TEST_SECRET_KEY", "test-only-secret-key-not-for-production")
TEST_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "TestAdmin123!")
TEST_REGULAR_PASSWORD = os.environ.get("TEST_REGULAR_PASSWORD", "TestUser123!")
TEST_VIEWER_PASSWORD = os.environ.get("TEST_VIEWER_PASSWORD", "TestViewer123!")
TEST_INACTIVE_PASSWORD = os.environ.get("TEST_INACTIVE_PASSWORD", "TestInactive123!")
TEST_NEW_USER_PASSWORD = os.environ.get("TEST_NEW_USER_PASSWORD", "NewUser123!")
TEST_UNVERIFIED_COACH_PASSWORD = os.environ.get("TEST_UNVERIFIED_COACH_PASSWORD", "CoachVerify123!")
TEST_VALID_PASSWORD = os.environ.get("TEST_VALID_PASSWORD", "StrongPassword123!")
TEST_NEW_PASSWORD = os.environ.get("TEST_NEW_PASSWORD", "UpdatedCoach456!")
TEST_CURRENT_PASSWORD = os.environ.get("TEST_CURRENT_PASSWORD", "CurrentPass123!")
TEST_INVALID_PASSWORD = os.environ.get("TEST_INVALID_PASSWORD", "WrongPassword123!")
TEST_MISMATCH_PASSWORD = os.environ.get("TEST_MISMATCH_PASSWORD", "OtherPassword123!")
TEST_DIFFERENT_PASSWORD = os.environ.get("TEST_DIFFERENT_PASSWORD", "Different456!")
TEST_MISMATCH_CONFIRM_PASSWORD = os.environ.get("TEST_MISMATCH_CONFIRM_PASSWORD", "DifferentPassword123!")
TEST_WEAK_PASSWORD = os.environ.get("TEST_WEAK_PASSWORD", "weakpass")
TEST_WEAK_PASSWORD_LONG = os.environ.get("TEST_WEAK_PASSWORD_LONG", "password123")
TEST_VALID_COMPLEX_PASSWORD = os.environ.get("TEST_VALID_COMPLEX_PASSWORD", "Coach@123")
TEST_NEW_SECURE_PASSWORD = os.environ.get("TEST_NEW_SECURE_PASSWORD", "NewSecure456!")
TEST_OTP_CODE = os.environ.get("TEST_OTP_CODE", "123456")
TEST_PLACEHOLDER_HASH = os.environ.get("TEST_PLACEHOLDER_HASH", "hashed")

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("SECRET_KEY", TEST_SECRET_KEY)
os.environ.setdefault("SUPERADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
os.environ.setdefault("SUPERADMIN_EMAIL", os.environ.get("TEST_ADMIN_EMAIL", "admin@test.com"))
os.environ["BCRYPT_ROUNDS"] = "4"

from app.api.router import api_router
from app.core import database as database_module
from app.core.config import settings
from app.core.database import create_managed_tables
from app.core.error_handlers import register_exception_handlers
from app.core.security import create_access_token, hash_otp, hash_password
from app.models import Organization, User
from app.models.enums import UserRole

ADMIN_ID = UUID("00000000-0000-4000-8000-000000000001")
REGULAR_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
VIEWER_ID = UUID("00000000-0000-4000-8000-000000000003")
INACTIVE_ID = UUID("00000000-0000-4000-8000-000000000004")
SEEDED_ORG_ID = UUID("00000000-0000-4000-8000-000000000010")

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@test.com")
REGULAR_EMAIL = os.environ.get("TEST_REGULAR_EMAIL", "user@test.com")
VIEWER_EMAIL = os.environ.get("TEST_VIEWER_EMAIL", "viewer@test.com")
INACTIVE_EMAIL = os.environ.get("TEST_INACTIVE_EMAIL", "inactive@test.com")
NEW_USER_EMAIL = os.environ.get("TEST_NEW_USER_EMAIL", "newuser@test.com")

ADMIN_PASSWORD = TEST_ADMIN_PASSWORD
REGULAR_PASSWORD = TEST_REGULAR_PASSWORD
VIEWER_PASSWORD = TEST_VIEWER_PASSWORD
INACTIVE_PASSWORD = TEST_INACTIVE_PASSWORD
NEW_USER_PASSWORD = TEST_NEW_USER_PASSWORD

ORG_BASE = "/api/v1/super-admin/organizations"
USER_BASE = "/api/v1/super-admin/users"
DASHBOARD_BASE = "/api/v1/super-admin/dashboard"
REGISTER_BASE = "/api/v1/register"
VERIFY_BASE = "/api/v1/verify-email"
RESEND_BASE = "/api/v1/resend-verification-code"
COACH_LOGIN_BASE = "/api/v1/coach/login"
COACH_FORGOT_PASSWORD_BASE = "/api/v1/coach/forgot-password"
COACH_CANCEL_VERIFICATION_BASE = "/api/v1/coach/cancel-verification"
COACH_CONTINUE_VERIFICATION_BASE = "/api/v1/coach/continue-verification"

UNVERIFIED_COACH_ID = UUID("00000000-0000-4000-8000-000000000020")
UNVERIFIED_COACH_EMAIL = os.environ.get("TEST_UNVERIFIED_COACH_EMAIL", "unverified.coach@test.com")
UNVERIFIED_COACH_PASSWORD = TEST_UNVERIFIED_COACH_PASSWORD


def _sync_database_url() -> str:
    """Convert the app async DATABASE_URL into a psycopg2 URL for test setup."""
    parsed = make_url(os.environ["DATABASE_URL"])
    if str(parsed.drivername).endswith("+asyncpg") or parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg2")
    return parsed.render_as_string(hide_password=False)


def _rebind_async_engine_for_tests() -> None:
    """Use NullPool so TestClient event loops never reuse asyncpg connections."""
    database_module.engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    database_module.SessionLocal = async_sessionmaker(
        bind=database_module.engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


sync_engine = create_engine(_sync_database_url(), pool_pre_ping=True)


def auth_headers(token: str) -> dict[str, str]:
    """Return an Authorization header for the given JWT."""
    return {"Authorization": f"Bearer {token}"}


def make_expired_token(user_id: UUID) -> str:
    """Build an otherwise valid access JWT that has already expired."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid4()),
        "iat": now - timedelta(hours=48),
        "exp": now - timedelta(hours=1),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> Generator[None, None, None]:
    """Create organizations plus app-managed tables once per test session."""
    _rebind_async_engine_for_tests()
    with sync_engine.begin() as connection:
        Organization.__table__.create(connection, checkfirst=True)
        create_managed_tables(connection)
    yield
    asyncio.run(database_module.engine.dispose())
    sync_engine.dispose()


@pytest.fixture(scope="session")
def password_hashes() -> dict[str, str]:
    """Pre-hash fixture passwords once (bcrypt is expensive)."""
    return {
        ADMIN_PASSWORD: hash_password(ADMIN_PASSWORD),
        REGULAR_PASSWORD: hash_password(REGULAR_PASSWORD),
        VIEWER_PASSWORD: hash_password(VIEWER_PASSWORD),
        INACTIVE_PASSWORD: hash_password(INACTIVE_PASSWORD),
        NEW_USER_PASSWORD: hash_password(NEW_USER_PASSWORD),
    }


@pytest.fixture(autouse=True)
def mock_third_party_services() -> Generator[dict[str, Any], None, None]:
    """Block real SendGrid and Stripe HTTP calls for every test."""
    sendgrid_response = MagicMock()
    sendgrid_response.status_code = 202
    sendgrid_response.body = b'{"id": "mock-sg-message-id"}'
    sendgrid_response.headers = {}

    stripe_customer = {
        "id": "cus_test_123",
        "object": "customer",
        "email": ADMIN_EMAIL,
        "livemode": False,
    }

    with (
        patch("app.core.email.SendGridAPIClient") as sendgrid_cls,
        patch("app.core.email.send_email", return_value=None) as send_email,
        patch("app.core.email.send_password_reset_email", return_value=None),
        patch("app.core.email.send_verification_email", return_value=None),
        patch("app.services.email_verification.send_verification_email", return_value=None),
        patch("app.services.stripe_client.stripe") as stripe_mod,
    ):
        sendgrid_cls.return_value.send.return_value = sendgrid_response
        stripe_mod.Customer.create.return_value = stripe_customer
        stripe_mod.Customer.retrieve.return_value = stripe_customer
        yield {"send_email": send_email, "sendgrid": sendgrid_cls, "stripe": stripe_mod}


@pytest.fixture
def seeded_users(password_hashes: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Insert admin, regular, viewer, and inactive users; new user stays out of DB."""
    with sync_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE TABLE users, organizations RESTART IDENTITY CASCADE")
        )

    org = Organization(
        id=SEEDED_ORG_ID,
        name="Seeded Hoops Club",
        admin_email="seeded-org@test.com",
        phone_number="5551234567",
        address="1 Court Ave",
        join_code="SEEDOR01",
    )
    admin = User(
        id=ADMIN_ID,
        email=ADMIN_EMAIL,
        encrypted_password=password_hashes[ADMIN_PASSWORD],
        role=UserRole.SUPER_ADMIN.value,
        first_name="Admin",
        last_name="User",
        is_super_admin=True,
        is_active=True,
        org_id=None,
    )
    regular = User(
        id=REGULAR_USER_ID,
        email=REGULAR_EMAIL,
        username="regularcoach",
        encrypted_password=password_hashes[REGULAR_PASSWORD],
        role=UserRole.COACH.value,
        first_name="Regular",
        last_name="Coach",
        is_super_admin=False,
        is_active=True,
        org_id=SEEDED_ORG_ID,
        email_confirmed_at=datetime.now(timezone.utc),
    )
    viewer = User(
        id=VIEWER_ID,
        email=VIEWER_EMAIL,
        encrypted_password=password_hashes[VIEWER_PASSWORD],
        role=UserRole.PLAYER.value,
        first_name="Viewer",
        last_name="Player",
        is_super_admin=False,
        is_active=True,
        org_id=SEEDED_ORG_ID,
    )
    inactive = User(
        id=INACTIVE_ID,
        email=INACTIVE_EMAIL,
        encrypted_password=password_hashes[INACTIVE_PASSWORD],
        role=UserRole.COACH.value,
        first_name="Inactive",
        last_name="Coach",
        is_super_admin=False,
        is_active=False,
        org_id=None,
    )

    with Session(sync_engine) as session:
        session.add_all([org, admin, regular, viewer, inactive])
        session.commit()

    return {
        "admin": {
            "id": ADMIN_ID,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "role": "super_admin",
            "token": create_access_token(ADMIN_ID),
        },
        "user": {
            "id": REGULAR_USER_ID,
            "email": REGULAR_EMAIL,
            "password": REGULAR_PASSWORD,
            "role": "coach",
            "token": create_access_token(REGULAR_USER_ID),
        },
        "viewer": {
            "id": VIEWER_ID,
            "email": VIEWER_EMAIL,
            "password": VIEWER_PASSWORD,
            "role": "player",
            "token": create_access_token(VIEWER_ID),
        },
        "inactive": {
            "id": INACTIVE_ID,
            "email": INACTIVE_EMAIL,
            "password": INACTIVE_PASSWORD,
            "role": "coach",
            "token": create_access_token(INACTIVE_ID),
            "is_active": False,
        },
        "new": {
            "email": NEW_USER_EMAIL,
            "password": NEW_USER_PASSWORD,
            "role": "coach",
            "first_name": "New",
            "last_name": "User",
        },
    }


@pytest.fixture
def admin_headers(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Authorization header for the super-admin fixture user."""
    return auth_headers(seeded_users["admin"]["token"])


@pytest.fixture
def user_headers(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Authorization header for the regular coach fixture user."""
    return auth_headers(seeded_users["user"]["token"])


@pytest.fixture
def viewer_headers(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Authorization header for the readonly player fixture user."""
    return auth_headers(seeded_users["viewer"]["token"])


@pytest.fixture
def inactive_headers(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Authorization header for the deactivated fixture user."""
    return auth_headers(seeded_users["inactive"]["token"])


@pytest.fixture
def unverified_coach_user(password_hashes: dict[str, str]) -> User:
    """Coach awaiting email verification with a known OTP hash."""
    now = datetime.now(timezone.utc)
    with Session(sync_engine) as session:
        existing = session.get(User, UNVERIFIED_COACH_ID)
        if existing is None:
            user = User(
                id=UNVERIFIED_COACH_ID,
                email=UNVERIFIED_COACH_EMAIL,
                username="unverifiedcoach",
                encrypted_password=hash_password(UNVERIFIED_COACH_PASSWORD),
                role=UserRole.COACH.value,
                first_name="Unverified",
                last_name="Coach",
                is_super_admin=False,
                is_active=True,
                org_id=None,
                email_confirmed_at=None,
                confirmation_token=hash_otp(TEST_OTP_CODE),
                confirmation_sent_at=now,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

        existing.email = UNVERIFIED_COACH_EMAIL
        existing.username = "unverifiedcoach"
        existing.encrypted_password = hash_password(UNVERIFIED_COACH_PASSWORD)
        existing.email_confirmed_at = None
        existing.confirmation_token = hash_otp(TEST_OTP_CODE)
        existing.confirmation_sent_at = now
        existing.is_active = True
        existing.deleted_at = None
        session.commit()
        session.refresh(existing)
        return existing


@pytest.fixture
def unverified_coach_headers(unverified_coach_user: User) -> dict[str, str]:
    """JWT auth header for the unverified coach fixture."""
    token = create_access_token(
        unverified_coach_user.id,
        extra_claims={"email": unverified_coach_user.email, "role": unverified_coach_user.role},
    )
    return auth_headers(token)


@pytest.fixture
def new_user_payload(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Registration payload for the user that is not yet in the database."""
    newbie = seeded_users["new"]
    return {
        "first_name": newbie["first_name"],
        "last_name": newbie["last_name"],
        "email": newbie["email"],
        "password": newbie["password"],
        "role": newbie["role"],
    }


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Minimal FastAPI app with admin routers and the real get_db dependency."""
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(api_router, prefix="/api/v1")
    return test_app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """One TestClient (one event loop) for the session so asyncpg is not rebound."""
    with TestClient(app) as test_client:
        yield test_client
