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
    os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:1234@localhost:5432/hoops-engine-db"),
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
RESET_PASSWORD_BASE = "/api/v1/reset-password"
VALIDATE_PASSWORD_BASE = "/api/v1/reset-password/validate"
SESSIONS_BASE = "/api/v1/sessions"
LEADERBOARD_BASE = "/api/v1/leaderboard"
PRACTICE_PLANS_BASE = "/api/v1/practice-plans"
COACH_PRACTICE_PLANS_BASE = "/api/v1/coach/practice-plans"
DRILLS_SEARCH_BASE = "/api/v1/drills/search"
SUBSCRIPTION_BASE = "/api/v1/subscription"
PROFILE_BASE = "/api/v1/profile"

UNVERIFIED_COACH_ID = UUID("00000000-0000-4000-8000-000000000020")
OTHER_COACH_ID = UUID("00000000-0000-4000-8000-000000000021")
SEEDED_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000030")
SEEDED_FIELD_DRILL_ID = UUID("00000000-0000-4000-8000-000000000031")
SEEDED_FT_DRILL_ID = UUID("00000000-0000-4000-8000-000000000032")
SEEDED_PLAYER_JANE_ID = UUID("00000000-0000-4000-8000-000000000033")
SEEDED_PLAYER_BOB_ID = UUID("00000000-0000-4000-8000-000000000034")
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


@pytest.fixture(scope="session", autouse=True)
def _ensure_support_request_phone_column(_ensure_schema: None) -> Generator[None, None, None]:
    """Ensure phone column exists on support_requests for contact support tests."""
    with sync_engine.begin() as connection:
        exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'support_requests_staging'
                      AND column_name = 'phone'
                )
                """
            ),
        ).scalar()
        if not exists:
            connection.execute(
                text(
                    "ALTER TABLE support_requests_staging "
                    "ADD COLUMN phone VARCHAR(32) NULL"
                )
            )
    yield


@pytest.fixture(scope="session", autouse=True)
def _ensure_user_profile_columns(_ensure_schema: None) -> Generator[None, None, None]:
    """Ensure extended profile columns exist on users for profile API tests."""
    with sync_engine.begin() as connection:
        for column, ddl in (
            ("date_of_birth", "ALTER TABLE users ADD COLUMN date_of_birth DATE"),
            ("gender", "ALTER TABLE users ADD COLUMN gender TEXT"),
            ("grade", "ALTER TABLE users ADD COLUMN grade TEXT"),
            ("parent_guardian", "ALTER TABLE users ADD COLUMN parent_guardian TEXT"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'users'
                          AND column_name = :column_name
                    )
                    """
                ),
                {"column_name": column},
            ).scalar()
            if not exists:
                connection.execute(text(ddl))
    yield


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
        patch("app.services.registration.send_verification_email", return_value=None),
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
def coach_headers(user_headers: dict[str, str]) -> dict[str, str]:
    """Authorization header for the verified coach fixture user."""
    return user_headers


@pytest.fixture
def ensure_practice_sessions_table(seeded_users: dict[str, dict[str, Any]]) -> Generator[None, None, None]:
    """Ensure practice_sessions exists with session recording columns for coach API tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.practice_sessions (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id uuid NOT NULL REFERENCES public.organizations(id),
                    team_id uuid,
                    subteam_id uuid,
                    session_date date NOT NULL DEFAULT CURRENT_DATE,
                    recorder_type text,
                    recorder_player_id uuid,
                    recorder_coach_id uuid,
                    session_code_used uuid,
                    device_id text,
                    synced boolean DEFAULT true,
                    created_at timestamptz DEFAULT now(),
                    session_mode text,
                    session_details jsonb,
                    recorder_user_id uuid,
                    status text DEFAULT 'in_progress',
                    started_at timestamptz,
                    ended_at timestamptz,
                    current_drill_index integer DEFAULT 0,
                    practice_plan_id uuid
                )
                """
            )
        )
        for column, ddl in (
            ("session_mode", "ALTER TABLE practice_sessions ADD COLUMN session_mode text"),
            ("session_details", "ALTER TABLE practice_sessions ADD COLUMN session_details jsonb"),
            ("recorder_user_id", "ALTER TABLE practice_sessions ADD COLUMN recorder_user_id uuid"),
            ("status", "ALTER TABLE practice_sessions ADD COLUMN status text DEFAULT 'in_progress'"),
            ("started_at", "ALTER TABLE practice_sessions ADD COLUMN started_at timestamptz"),
            ("ended_at", "ALTER TABLE practice_sessions ADD COLUMN ended_at timestamptz"),
            (
                "current_drill_index",
                "ALTER TABLE practice_sessions ADD COLUMN current_drill_index integer DEFAULT 0",
            ),
            ("practice_plan_id", "ALTER TABLE practice_sessions ADD COLUMN practice_plan_id uuid"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'practice_sessions'
                          AND column_name = :column_name
                    )
                    """
                ),
                {"column_name": column},
            ).scalar()
            if not exists:
                connection.execute(text(ddl))

        connection.execute(text("DELETE FROM practice_sessions"))
    yield


@pytest.fixture
def seed_session_summary_data(
    ensure_practice_sessions_table: None,
    seeded_users: dict[str, dict[str, Any]],
    password_hashes: dict[str, str],
) -> dict[str, Any]:
    """Seed a practice session with player stats for summary API tests."""
    from datetime import timedelta

    session_id = UUID("00000000-0000-4000-8000-000000000040")
    started_at = datetime.now(timezone.utc) - timedelta(minutes=9, seconds=41)

    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.players (
                    id uuid PRIMARY KEY,
                    org_id uuid,
                    first_name text NOT NULL,
                    last_name text NOT NULL,
                    player_code text UNIQUE,
                    active boolean DEFAULT true,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drills (
                    id uuid PRIMARY KEY,
                    name text NOT NULL,
                    category text NOT NULL,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.session_data (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id uuid,
                    org_id uuid NOT NULL,
                    player_id uuid NOT NULL,
                    drill_id uuid,
                    makes integer NOT NULL DEFAULT 0,
                    attempts integer NOT NULL DEFAULT 0,
                    session_date date NOT NULL DEFAULT CURRENT_DATE,
                    recorded_at timestamptz DEFAULT now(),
                    synced boolean DEFAULT true
                )
                """
            )
        )

        other_coach_email = "other.coach@test.com"
        connection.execute(
            text("DELETE FROM session_data WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        connection.execute(
            text("DELETE FROM practice_sessions WHERE id = :session_id"),
            {"session_id": session_id},
        )
        connection.execute(text("DELETE FROM users WHERE id = :coach_id"), {"coach_id": OTHER_COACH_ID})

        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, username, encrypted_password, role,
                    first_name, last_name, is_super_admin, is_active, org_id, email_confirmed_at
                ) VALUES (
                    :id, :email, :username, :password, :role,
                    :first_name, :last_name, false, true, :org_id, NOW()
                )
                """
            ),
            {
                "id": OTHER_COACH_ID,
                "email": other_coach_email,
                "username": "othercoach",
                "password": password_hashes[REGULAR_PASSWORD],
                "role": UserRole.COACH.value,
                "first_name": "Other",
                "last_name": "Coach",
                "org_id": SEEDED_ORG_ID,
            },
        )

        connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id, org_id, session_date, session_mode, recorder_user_id,
                    recorder_type, status, started_at, current_drill_index, synced, created_at
                ) VALUES (
                    :id, :org_id, CURRENT_DATE, 'one_drill', :recorder_user_id,
                    'coach', 'in_progress', :started_at, 0, true, :started_at
                )
                """
            ),
            {
                "id": session_id,
                "org_id": SEEDED_ORG_ID,
                "recorder_user_id": REGULAR_USER_ID,
                "started_at": started_at,
            },
        )

        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code)
                VALUES (:id, :org_id, 'Charlie', 'Hudson', 'PC-CHARLIE1')
                ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name
                """
            ),
            {"id": SEEDED_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO drills (id, name, category)
                VALUES
                    (:field_id, 'Spot Up', 'shooting'),
                    (:ft_id, 'Free Throw Line', 'free_throw'),
                    ('00000000-0000-4000-8000-000000000041', 'Warm-up Lap', 'general'),
                    ('00000000-0000-4000-8000-000000000042', 'Free Throw Set', 'free_throw'),
                    ('00000000-0000-4000-8000-000000000043', '3-Point Corner', 'shooting'),
                    ('00000000-0000-4000-8000-000000000044', 'Defensive Slides', 'defense')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"field_id": SEEDED_FIELD_DRILL_ID, "ft_id": SEEDED_FT_DRILL_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO session_data (
                    id, session_id, org_id, player_id, drill_id, makes, attempts
                ) VALUES
                    (gen_random_uuid(), :session_id, :org_id, :player_id, :field_drill, 6, 10),
                    (gen_random_uuid(), :session_id, :org_id, :player_id, :ft_drill, 4, 5)
                """
            ),
            {
                "session_id": session_id,
                "org_id": SEEDED_ORG_ID,
                "player_id": SEEDED_PLAYER_ID,
                "field_drill": SEEDED_FIELD_DRILL_ID,
                "ft_drill": SEEDED_FT_DRILL_ID,
            },
        )

    other_coach_token = create_access_token(OTHER_COACH_ID)
    return {
        "session_id": session_id,
        "other_coach_headers": auth_headers(other_coach_token),
    }


@pytest.fixture
def seed_leaderboard_data(seed_session_summary_data: dict[str, Any]) -> dict[str, Any]:
    """Seed multiple players with stats for leaderboard API tests."""
    session_id = seed_session_summary_data["session_id"]

    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code)
                VALUES
                    (:jane_id, :org_id, 'Jane', 'Doe', 'PC-JANEDOE1'),
                    (:bob_id, :org_id, 'Bob', 'Smith', 'PC-BOBSMIT1')
                ON CONFLICT (id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name
                """
            ),
            {
                "jane_id": SEEDED_PLAYER_JANE_ID,
                "bob_id": SEEDED_PLAYER_BOB_ID,
                "org_id": SEEDED_ORG_ID,
            },
        )
        connection.execute(
            text("DELETE FROM session_data WHERE player_id IN (:jane_id, :bob_id)"),
            {"jane_id": SEEDED_PLAYER_JANE_ID, "bob_id": SEEDED_PLAYER_BOB_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO session_data (
                    id, session_id, org_id, player_id, drill_id, makes, attempts
                ) VALUES
                    (gen_random_uuid(), :session_id, :org_id, :jane_id, :field_drill, 8, 10),
                    (gen_random_uuid(), :session_id, :org_id, :bob_id, :field_drill, 20, 30)
                """
            ),
            {
                "session_id": session_id,
                "org_id": SEEDED_ORG_ID,
                "jane_id": SEEDED_PLAYER_JANE_ID,
                "bob_id": SEEDED_PLAYER_BOB_ID,
                "field_drill": SEEDED_FIELD_DRILL_ID,
            },
        )

    return {
        **seed_session_summary_data,
        "jane_id": SEEDED_PLAYER_JANE_ID,
        "bob_id": SEEDED_PLAYER_BOB_ID,
    }


@pytest.fixture
def ensure_practice_plans_table(seeded_users: dict[str, dict[str, Any]]) -> Generator[None, None, None]:
    """Ensure practice plan client tables exist for coach practice plan API tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drills (
                    id uuid PRIMARY KEY,
                    name text NOT NULL,
                    category text NOT NULL,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.practice_plans (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    name text NOT NULL,
                    org_id uuid,
                    created_by_user uuid,
                    created_by_name text,
                    drill_count integer DEFAULT 0,
                    created_at timestamptz DEFAULT now(),
                    active boolean DEFAULT true
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.practice_plan_drills (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    plan_id uuid REFERENCES public.practice_plans(id),
                    drill_id uuid,
                    drill_name text,
                    reps integer DEFAULT 1,
                    order_num integer DEFAULT 0
                )
                """
            )
        )
        active_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'practice_plans'
                      AND column_name = 'active'
                )
                """
            )
        ).scalar()
        if not active_exists:
            connection.execute(
                text("ALTER TABLE practice_plans ADD COLUMN active boolean DEFAULT true")
            )

        approved_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'drills'
                      AND column_name = 'approved'
                )
                """
            )
        ).scalar()
        if not approved_exists:
            connection.execute(
                text("ALTER TABLE drills ADD COLUMN approved boolean DEFAULT true")
            )

        connection.execute(text("DELETE FROM practice_plan_drills"))
        connection.execute(text("DELETE FROM practice_plans"))
        connection.execute(text("DELETE FROM drills"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.players (
                    id uuid PRIMARY KEY,
                    org_id uuid,
                    first_name text NOT NULL,
                    last_name text NOT NULL,
                    player_code text UNIQUE,
                    jersey_number text,
                    active boolean DEFAULT true,
                    created_at timestamptz DEFAULT now()
                )
                """
            )
        )
        jersey_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'players'
                      AND column_name = 'jersey_number'
                )
                """
            )
        ).scalar()
        if not jersey_exists:
            connection.execute(text("ALTER TABLE players ADD COLUMN jersey_number text"))

        active_player_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'players'
                      AND column_name = 'active'
                )
                """
            )
        ).scalar()
        if not active_player_exists:
            connection.execute(text("ALTER TABLE players ADD COLUMN active boolean DEFAULT true"))

        connection.execute(text("DELETE FROM players"))
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code, jersey_number, active)
                VALUES
                    (:jane_id, :org_id, 'Jane', 'Hudson', 'PC-JANE001', '23', true),
                    (:bob_id, :org_id, 'Bob', 'Smith', 'PC-BOB001', '7', true),
                    ('00000000-0000-4000-8000-000000000035', :org_id, 'Inactive', 'Player', 'PC-INACT01', '99', false)
                """
            ),
            {
                "org_id": SEEDED_ORG_ID,
                "jane_id": SEEDED_PLAYER_JANE_ID,
                "bob_id": SEEDED_PLAYER_BOB_ID,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO drills (id, name, category, approved)
                VALUES
                    (:field_id, 'Spot Up', 'shooting', true),
                    (:ft_id, 'Free Throw Line', 'free_throw', true),
                    ('00000000-0000-4000-8000-000000000041', 'Warm-up Lap', 'general', true),
                    ('00000000-0000-4000-8000-000000000042', 'Free Throw Set', 'free_throw', true),
                    ('00000000-0000-4000-8000-000000000043', '3-Point Corner', 'shooting', true),
                    ('00000000-0000-4000-8000-000000000044', 'Defensive Slides', 'defense', true),
                    ('00000000-0000-4000-8000-000000000045', 'Inactive Spot Up', 'shooting', false)
                """
            ),
            {"field_id": SEEDED_FIELD_DRILL_ID, "ft_id": SEEDED_FT_DRILL_ID},
        )
    yield


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
def expired_user_headers(seeded_users: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Authorization header with an expired JWT for auth failure tests."""
    return auth_headers(make_expired_token(seeded_users["user"]["id"]))


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
