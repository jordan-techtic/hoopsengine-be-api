"""Quick schema verification after bootstrap + alembic."""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def main() -> None:
    async with engine.connect() as conn:
        ver = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='organizations' "
                "ORDER BY column_name"
            )
        )
        cols = [r[0] for r in result.fetchall()]
        users = await conn.scalar(text("SELECT COUNT(*) FROM users"))
        print(f"Alembic version: {ver}")
        print(f"organizations columns: {', '.join(cols)}")
        print(f"users count: {users}")
        assert "profile_description" in cols, "missing profile_description"
        assert "contact_info" in cols, "missing contact_info"
        print("Schema sync OK")


if __name__ == "__main__":
    asyncio.run(main())
