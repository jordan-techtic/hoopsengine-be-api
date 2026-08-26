import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.core.database import engine


async def table_exists(connection, table_name: str) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
    )


async def rename_users_table() -> None:
    async with engine.begin() as connection:
        has_old = await table_exists(connection, "users_he")
        has_new = await table_exists(connection, "users_staging")

        if has_old and has_new:
            row_count = await connection.scalar(text("SELECT COUNT(*) FROM users_staging"))
            if row_count == 0:
                await connection.execute(text("DROP TABLE users_staging"))
                print("Dropped empty users_staging table.")
            else:
                raise RuntimeError(
                    "Both users_he and users_staging exist with data. "
                    "Resolve manually before running this script."
                )

        if not await table_exists(connection, "users_he"):
            if await table_exists(connection, "users_staging"):
                print("users_staging already exists; nothing to rename.")
            else:
                print("Neither users_he nor users_staging found.")
            return

        await connection.execute(text("ALTER TABLE users_he RENAME TO users_staging"))

        rename_ops = [
            ("ALTER TABLE users_staging RENAME CONSTRAINT users_he_pkey TO users_staging_pkey", "users_he_pkey"),
            (
                "ALTER TABLE users_staging RENAME CONSTRAINT users_he_role_check TO users_staging_role_check",
                "users_he_role_check",
            ),
            ("ALTER INDEX ix_users_he_email RENAME TO ix_users_staging_email", "ix_users_he_email"),
            ("ALTER INDEX ix_users_he_role RENAME TO ix_users_staging_role", "ix_users_he_role"),
            ("ALTER INDEX ix_users_he_org_id RENAME TO ix_users_staging_org_id", "ix_users_he_org_id"),
        ]
        for statement, _name in rename_ops:
            try:
                await connection.execute(text(statement))
            except Exception as exc:
                print(f"Skipped: {statement} ({exc.__class__.__name__})")

    print("Renamed users_he to users_staging.")


if __name__ == "__main__":
    asyncio.run(rename_users_table())
