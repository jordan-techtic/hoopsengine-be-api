import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, create_managed_tables, engine
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.organization import Organization  # noqa: F401
from app.models.user import User

LEGACY_SUPERADMIN_EMAILS = (
    "admin@hoopsengine.com",
    "admin.hoopsengine@yopmail.com",
)


async def create_superadmin() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(create_managed_tables)

    email = settings.SUPERADMIN_EMAIL.lower()
    password_hash = hash_password(settings.SUPERADMIN_PASSWORD)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            for legacy_email in LEGACY_SUPERADMIN_EMAILS:
                if legacy_email == email:
                    continue
                legacy_result = await session.execute(
                    select(User).where(User.email == legacy_email)
                )
                user = legacy_result.scalar_one_or_none()
                if user is not None:
                    user.email = email
                    break

        if user is None:
            session.add(
                User(
                    email=email,
                    encrypted_password=password_hash,
                    role=UserRole.SUPER_ADMIN.value,
                    first_name=settings.SUPERADMIN_FIRST_NAME,
                    last_name=settings.SUPERADMIN_LAST_NAME,
                    is_super_admin=True,
                    is_active=True,
                    email_confirmed_at=now,
                )
            )
            await session.commit()
            print(f"Created superadmin: {email}")
            return

        user.encrypted_password = password_hash
        user.role = UserRole.SUPER_ADMIN.value
        user.is_super_admin = True
        user.is_active = True
        user.deleted_at = None
        user.first_name = user.first_name or settings.SUPERADMIN_FIRST_NAME
        user.last_name = user.last_name or settings.SUPERADMIN_LAST_NAME
        user.email_confirmed_at = user.email_confirmed_at or now
        await session.commit()
        print(f"Updated existing superadmin: {email}")


if __name__ == "__main__":
    asyncio.run(create_superadmin())
