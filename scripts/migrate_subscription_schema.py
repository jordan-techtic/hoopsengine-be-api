import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import engine
from app.core.schema_migrations import run_subscription_schema_migrations


async def main() -> None:
    async with engine.begin() as connection:
        await run_subscription_schema_migrations(connection)
    print("Subscription schema migrations completed.")


if __name__ == "__main__":
    asyncio.run(main())
