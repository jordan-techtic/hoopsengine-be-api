"""
One-off: rename public.users_staging → public.users on the configured DATABASE_URL.

Prefer starting the API (auto-migration) or:
  python scripts/rename_users_staging_to_users.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import engine
from app.core.schema_migrations import migrate_users_staging_to_users


async def main() -> None:
    async with engine.begin() as connection:
        await migrate_users_staging_to_users(connection)
    print("users table migration finished.")


if __name__ == "__main__":
    asyncio.run(main())
