import asyncio
import logging
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.tables import USERS_TABLE
from app.core.database import SessionLocal, engine
from app.models.enums import UserRole
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ROLE_MAP = {
    "admin": UserRole.ORG_ADMIN.value,
    "player": UserRole.PLAYER.value,
    "coach": UserRole.COACH.value,
    "org_admin": UserRole.ORG_ADMIN.value,
    "super_admin": UserRole.SUPER_ADMIN.value,
}


def names_from_meta(meta: Any) -> tuple[str | None, str | None]:
    if not isinstance(meta, dict):
        return None, None
    first = meta.get("first_name") or meta.get("given_name") or meta.get("name")
    last = meta.get("last_name") or meta.get("family_name")
    if isinstance(first, str):
        first = first.strip() or None
    else:
        first = None
    if isinstance(last, str):
        last = last.strip() or None
    else:
        last = None
    return first, last


def resolve_role(
    *,
    is_super_admin: bool | None,
    user_role: str | None,
    is_coach: bool,
    is_player: bool,
) -> str:
    if is_super_admin:
        return UserRole.SUPER_ADMIN.value
    if is_coach:
        return UserRole.COACH.value
    if user_role:
        mapped = ROLE_MAP.get(user_role.lower())
        if mapped:
            return mapped
    if is_player or user_role == "player":
        return UserRole.PLAYER.value
    if user_role == "admin":
        return UserRole.ORG_ADMIN.value
    return UserRole.PLAYER.value


async def fetch_source_users() -> list[dict[str, Any]]:
    query = text(
        """
        SELECT
            au.id,
            lower(trim(au.email)) AS email,
            au.encrypted_password,
            au.role AS auth_role,
            au.is_super_admin,
            au.phone,
            au.email_confirmed_at,
            au.recovery_token,
            au.recovery_sent_at,
            au.last_sign_in_at,
            au.banned_until,
            au.deleted_at,
            au.raw_user_meta_data,
            au.created_at,
            au.updated_at,
            ur.role AS app_role,
            ur.org_id,
            EXISTS (
                SELECT 1
                FROM coaches c
                WHERE lower(trim(c.email)) = lower(trim(au.email))
            ) AS is_coach,
            EXISTS (
                SELECT 1
                FROM players p
                WHERE p.user_id = au.id
            ) AS is_player,
            c.first_name AS coach_first_name,
            c.last_name AS coach_last_name
        FROM auth.users au
        LEFT JOIN user_roles ur ON ur.user_id = au.id
        LEFT JOIN coaches c ON lower(trim(c.email)) = lower(trim(au.email))
        WHERE au.email IS NOT NULL
          AND trim(au.email) <> ''
        ORDER BY au.created_at NULLS LAST, au.id
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(query)
        rows = [dict(row._mapping) for row in result]

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        email = row["email"]
        current = deduped.get(email)
        if current is None:
            deduped[email] = row
            continue

        # Prefer rows that include org/role context.
        if current.get("org_id") is None and row.get("org_id") is not None:
            current["org_id"] = row["org_id"]
        if current.get("app_role") is None and row.get("app_role") is not None:
            current["app_role"] = row["app_role"]
        if not current.get("is_coach") and row.get("is_coach"):
            current["is_coach"] = True
            current["coach_first_name"] = row.get("coach_first_name")
            current["coach_last_name"] = row.get("coach_last_name")
        if not current.get("is_player") and row.get("is_player"):
            current["is_player"] = True

    return list(deduped.values())


def build_staging_record(source: dict[str, Any]) -> dict[str, Any] | None:
    email = source.get("email")
    password = source.get("encrypted_password")
    if not email or not password:
        return None

    meta_first, meta_last = names_from_meta(source.get("raw_user_meta_data"))
    role = resolve_role(
        is_super_admin=bool(source.get("is_super_admin")),
        user_role=source.get("app_role") or source.get("auth_role"),
        is_coach=bool(source.get("is_coach")),
        is_player=bool(source.get("is_player")),
    )

    deleted_at = source.get("deleted_at")
    banned_until = source.get("banned_until")

    return {
        "id": source["id"],
        "email": email,
        "encrypted_password": password,
        "role": role,
        "org_id": source.get("org_id"),
        "first_name": source.get("coach_first_name") or meta_first,
        "last_name": source.get("coach_last_name") or meta_last,
        "phone": source.get("phone"),
        "is_super_admin": bool(source.get("is_super_admin")),
        "is_active": deleted_at is None and banned_until is None,
        "email_confirmed_at": source.get("email_confirmed_at"),
        "recovery_token": source.get("recovery_token"),
        "recovery_sent_at": source.get("recovery_sent_at"),
        "last_sign_in_at": source.get("last_sign_in_at"),
        "banned_until": banned_until,
        "deleted_at": deleted_at,
        "raw_user_meta_data": source.get("raw_user_meta_data"),
        "created_at": source.get("created_at"),
        "updated_at": source.get("updated_at"),
    }


async def upsert_users(records: list[dict[str, Any]]) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    skipped = 0

    async with SessionLocal() as session:
        for record in records:
            built = build_staging_record(record)
            if built is None:
                skipped += 1
                continue

            existing = await session.scalar(
                select(User.id).where(User.email == built["email"])
            )
            stmt = insert(User).values(**built)
            stmt = stmt.on_conflict_do_update(
                index_elements=[User.email],
                set_={
                    "encrypted_password": stmt.excluded.encrypted_password,
                    "role": stmt.excluded.role,
                    "org_id": stmt.excluded.org_id,
                    "first_name": stmt.excluded.first_name,
                    "last_name": stmt.excluded.last_name,
                    "phone": stmt.excluded.phone,
                    "is_super_admin": stmt.excluded.is_super_admin,
                    "is_active": stmt.excluded.is_active,
                    "email_confirmed_at": stmt.excluded.email_confirmed_at,
                    "recovery_token": stmt.excluded.recovery_token,
                    "recovery_sent_at": stmt.excluded.recovery_sent_at,
                    "last_sign_in_at": stmt.excluded.last_sign_in_at,
                    "banned_until": stmt.excluded.banned_until,
                    "deleted_at": stmt.excluded.deleted_at,
                    "raw_user_meta_data": stmt.excluded.raw_user_meta_data,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await session.execute(stmt)
            if existing:
                updated += 1
            else:
                inserted += 1

        await session.commit()

    return inserted, updated, skipped


async def sync_users_to_staging() -> None:
    sources = await fetch_source_users()
    logger.info("Found %s users in auth.users", len(sources))

    inserted, updated, skipped = await upsert_users(sources)

    async with engine.connect() as connection:
        staging_count = await connection.scalar(
            text(f"SELECT COUNT(*) FROM {USERS_TABLE}")
        )

    logger.info("Inserted: %s", inserted)
    logger.info("Updated: %s", updated)
    logger.info("Skipped (missing email/password): %s", skipped)
    logger.info("%s total rows: %s", USERS_TABLE, staging_count)


if __name__ == "__main__":
    asyncio.run(sync_users_to_staging())
