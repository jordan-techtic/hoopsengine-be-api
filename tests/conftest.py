import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/hoops_engine_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-organizations-api")
os.environ.setdefault("SUPERADMIN_PASSWORD", "TestPass123!")
