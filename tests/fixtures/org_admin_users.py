"""Shared org-admin test user fixtures for HE-448-HE-453 integration tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    SEEDED_ORG_ID,
    TEST_VALID_PASSWORD,
    auth_headers,
    create_access_token,
    sync_engine,
)


def seed_org_admin(*, user_id: UUID, email: str, username: str, org_id: UUID = SEEDED_ORG_ID) -> dict[str, str]:
    with Session(sync_engine) as session:
        if session.get(User, user_id) is None:
            session.add(
                User(
                    id=user_id,
                    email=email,
                    username=username,
                    encrypted_password=hash_password(TEST_VALID_PASSWORD),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Org",
                    last_name="Admin",
                    is_super_admin=False,
                    is_active=True,
                    org_id=org_id,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    return auth_headers(create_access_token(user_id))
