Existing tests/conftest.py provides PostgreSQL test infrastructure:
- TEST_DATABASE_URL from .env.test (postgresql+asyncpg)
- FastAPI TestClient fixture (client)
- seeded_users with 5 roles: admin, user, viewer, inactive, new
- auth_headers, admin_headers, user_headers, viewer_headers, inactive_headers
- ensure_teams_table, ensure_practice_plans_table client-domain bootstrapping
- Route base constants (TEAMS_BASE, ORG_ADMIN_*_BASE, etc.)

No conftest changes required; new tests import from tests/conftest.py directly.