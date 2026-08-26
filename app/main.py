import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.logging_config import setup_logging

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import (
    create_managed_tables,
    engine,
    verify_database_connection,
    verify_users_table,
)
from app.core.error_handlers import register_exception_handlers
from app.core.openapi import setup_openapi
from app.core.schema_migrations import run_subscription_schema_migrations
from app.models import (  # noqa: F401
    Organization,
    RevokedToken,
    StripeSubscription,
    SubscriptionPlan,
    SupportRequest,
    User,
)

setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Connectivity only first — managed tables may still need create_all.
    await verify_database_connection(require_users_table=False)
    async with engine.begin() as connection:
        await run_subscription_schema_migrations(connection)
        # App-owned tables only (`users` + other managed tables).
        await connection.run_sync(create_managed_tables)
    await verify_users_table()
    logger.info("Database tables verified")
    yield
    await engine.dispose()
    logger.info("Database connection closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
)

register_exception_handlers(app)
setup_openapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": settings.APP_NAME,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="debug" if settings.DEBUG else "info",
    )
