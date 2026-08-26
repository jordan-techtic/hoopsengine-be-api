import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url

# Add project root to path so models can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def to_sync_database_url(url: str) -> str:
    """Alembic must use a sync driver; convert asyncpg URLs to psycopg2."""
    parsed = make_url(url)
    driver = parsed.drivername
    if driver.endswith("+asyncpg") or driver == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg2")
    elif driver.endswith("+aiosqlite"):
        parsed = parsed.set(drivername="sqlite")
    return parsed.render_as_string(hide_password=False)


database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set; load it from the environment or .env")
# ConfigParser interpolates '%'; escape so passwords with '%' survive.
config.set_main_option("sqlalchemy.url", to_sync_database_url(database_url).replace("%", "%%"))

from app.core.database import Base
import app.models  # noqa: F401 — register models on Base.metadata

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a sync engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
