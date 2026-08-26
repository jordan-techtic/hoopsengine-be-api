import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.tables import MANAGED_TABLE_NAMES, USERS_TABLE

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_reset_on_return="rollback",
    connect_args={"statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_database_log_info() -> str:
    url = make_url(settings.DATABASE_URL)
    username = url.username or ""
    auth = f"{username}:****" if url.password else username
    host = url.host or "localhost"
    port = f":{url.port}" if url.port else ""
    database = url.database or ""
    return f"{url.drivername}://{auth}@{host}{port}/{database}"


def create_managed_tables(connection: Connection) -> None:
    """
    Create only app-managed tables (`users` + `*_staging` helpers).

    Client domain tables (organizations, drills, …) are owned by SQL bootstrap and
    must not be created from incomplete SQLAlchemy models.
    """
    managed = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in MANAGED_TABLE_NAMES
    ]
    Base.metadata.create_all(connection, tables=managed)


async def verify_users_table() -> None:
    table_name = USERS_TABLE
    async with engine.connect() as connection:
        exists = await connection.scalar(
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
        if not exists:
            raise RuntimeError(
                f"Configured users table '{table_name}' does not exist in the database. "
                "Run scripts/bootstrap_hoops_engine_db.py first."
            )
    logger.info("Users table verified: %s", table_name)


async def verify_database_connection(*, require_users_table: bool = True) -> None:
    logger.info("Connecting to database")

    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        result.scalar_one()

    logger.info("Database connection established successfully")
    if require_users_table:
        await verify_users_table()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
