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
from app.models import Organization, OrgBillingHistory, OrgPaymentMethod, OrgReport, OrgUiDesign, OrgUiDesignFeedback, User
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
COACH_REMOVE_PLAYER_BASE = "/api/v1/coach/remove_player"
COACH_CONFIRM_REMOVAL_BASE = "/api/v1/coach/confirm_removal"
RESET_PASSWORD_BASE = "/api/v1/reset-password"
VALIDATE_PASSWORD_BASE = "/api/v1/reset-password/validate"
SESSIONS_BASE = "/api/v1/sessions"
LEADERBOARD_BASE = "/api/v1/leaderboard"
PRACTICE_PLANS_BASE = "/api/v1/practice-plans"
PLAYERS_BASE = "/api/v1/players"
ATTENDANCE_BASE = "/api/v1/attendance"
ATTENDANCE_SEARCH_BASE = "/api/v1/attendance/players/search"
LIVE_PRACTICE_BASE = "/api/v1/live_practice"
COACH_PRACTICE_PLANS_BASE = "/api/v1/coach/practice-plans"
DRILLS_BASE = "/api/v1/drills"
COACH_DRILLS_BASE = "/api/v1/coach/drills"
DRILL_IDEAS_BASE = "/api/v1/drill-ideas"
COACH_QUEUE_BASE = "/api/v1/coach/queue"
COACH_SYNC_BASE = "/api/v1/coach/sync"
COACH_CLEAR_CACHE_BASE = "/api/v1/coach/clear-cache"
COACH_SYNC_PREFERENCES_BASE = "/api/v1/coach/sync/preferences"
COACH_SYNC_ACTIVITY_BASE = "/api/v1/coach/sync-activity"
COACH_HOME_BASE = "/api/v1/coach/home"
HOME_BASE = "/api/v1/home"
STATISTICS_BASE = "/api/v1/statistics"
DRILLS_SEARCH_BASE = "/api/v1/drills/search"
SUBSCRIPTION_BASE = "/api/v1/subscription"
WEBHOOKS_BASE = "/api/v1/webhooks"
PROFILE_BASE = "/api/v1/profile"
PLAYER_FORGOT_PASSWORD_BASE = "/api/v1/player/forgot-password"
PLAYER_VERIFY_CODE_BASE = "/api/v1/player/verify-code"
PLAYER_LOGIN_BASE = "/api/v1/login"
PLAYER_LOGIN_VALIDATE_BASE = "/api/v1/login/validate"
PLAYER_PROFILE_BASE = "/api/v1/player/profile"
PLAYER_RESET_PASSWORD_BASE = "/api/v1/player/reset-password"
PLAYER_RESET_PASSWORD_WITH_TOKEN_BASE = "/api/v1/player/reset-password-with-token"
REPORTS_BASE = "/api/v1/reports"
ANALYTICS_BASE = "/api/v1/analytics"
PLAYER_ROLE_SELECTION_BASE = "/api/v1/player/role-selection"
ORGANIZATION_PROFILE_BASE = "/api/v1/organization/profile"
ORG_ADMIN_LOGIN_BASE = "/api/v1/organization/login"
BILLING_HISTORY_BASE = "/api/v1/admin/billing/history"
BILLING_PAYMENT_METHOD_BASE = "/api/v1/admin/billing/payment-method"
BILLING_HISTORY_ALIAS_BASE = "/api/v1/billing/history"
BILLING_PAYMENT_METHOD_ALIAS_BASE = "/api/v1/billing/payment-method"
CUSTOM_UI_DESIGN_BASE = "/api/v1/custom-ui/design"
CUSTOM_UI_DESIGNS_BASE = "/api/v1/custom-ui/designs"
UI_DESIGN_SAVE_BASE = "/api/v1/ui-design/save"
UI_DESIGN_TEMPLATES_BASE = "/api/v1/ui-design/templates"
UI_DESIGN_FEEDBACK_BASE = "/api/v1/ui-design/feedback"
PLAYER_HOME_BASE = "/api/v1/player/home"
PLAYER_MY_PROGRESS_BASE = "/api/v1/player/my-progress"
PLAYER_SESSION_HISTORY_BASE = "/api/v1/player/session-history"
PLAYER_DRILL_PERFORMANCE_BASE = "/api/v1/player/drill-performance"
PLAYER_CANCEL_VERIFICATION_BASE = "/api/v1/player/cancel-verification"
PLAYER_CHANGE_PASSWORD_BASE = "/api/v1/player/change-password"
PLAYER_SUPPORT_INQUIRIES_BASE = "/api/v1/support/inquiries"
PLAYER_SUPPORT_CONTACT_BASE = "/api/v1/support/contact"
PLAYER_DRILL_SUBMISSIONS_BASE = "/api/v1/player/drill-submissions"
PLAYER_DRILLS_BASE = "/api/v1/player/drills"
PLAYER_START_BASE = "/api/v1/player/start"

UNVERIFIED_COACH_ID = UUID("00000000-0000-4000-8000-000000000020")
OTHER_COACH_ID = UUID("00000000-0000-4000-8000-000000000021")
SEEDED_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000030")
SEEDED_FIELD_DRILL_ID = UUID("00000000-0000-4000-8000-000000000031")
SEEDED_FT_DRILL_ID = UUID("00000000-0000-4000-8000-000000000032")
SEEDED_PLAYER_JANE_ID = UUID("00000000-0000-4000-8000-000000000033")
SEEDED_PLAYER_BOB_ID = UUID("00000000-0000-4000-8000-000000000034")
SEEDED_INVITATION_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000037")
SEEDED_REDEEMED_INVITATION_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000038")
SEEDED_VIEWER_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000042")
SEEDED_SUBTEAM_ID = UUID("00000000-0000-4000-8000-000000000040")
SEEDED_PLAYER_DRILL_ONE_ID = UUID("00000000-0000-4000-8000-000000000041")
SEEDED_PLAYER_DRILL_TWO_ID = UUID("00000000-0000-4000-8000-000000000043")
PLAYER_INVITATION_CODE = "PC-A1B2C3D4"
REDEEMED_PLAYER_INVITATION_CODE = "PC-B2C3D4E5"
UNVERIFIED_COACH_EMAIL = os.environ.get("TEST_UNVERIFIED_COACH_EMAIL", "unverified.coach@test.com")
UNVERIFIED_COACH_PASSWORD = TEST_UNVERIFIED_COACH_PASSWORD
UNVERIFIED_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000039")
UNVERIFIED_PLAYER_EMAIL = os.environ.get("TEST_UNVERIFIED_PLAYER_EMAIL", "unverified.player@test.com")
UNVERIFIED_PLAYER_PASSWORD = os.environ.get("TEST_UNVERIFIED_PLAYER_PASSWORD", "PlayerVerify123!")


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
       
# ... truncated; full file provides client, seeded_users, sync_engine, 5 base users ...