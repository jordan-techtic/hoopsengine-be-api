"""See tests/conftest.py — full PostgreSQL test infrastructure already present.

This module documents required fixtures for coach-module integration tests:
- seeded_users: admin, coach (regular), viewer/player, inactive, new (not in DB)
- mock_third_party_services: patches SendGrid + Stripe (autouse)
- client / app: FastAPI TestClient mounted at /api/v1
- coach_headers, admin_headers, viewer_headers, inactive_headers, expired_user_headers
- ensure_practice_sessions_table, ensure_practice_plans_table
- seed_session_summary_data, seed_leaderboard_data

Run: pytest tests/api/test_coach_module_acceptance.py -q
Requires: DATABASE_URL or TEST_DATABASE_URL pointing to PostgreSQL.
"""

# Re-export constants for convenience in acceptance test modules.
from tests.conftest import (  # noqa: F401
    LEADERBOARD_BASE,
    PRACTICE_PLANS_BASE,
    PROFILE_BASE,
    SESSIONS_BASE,
    auth_headers,
    coach_headers,
    seeded_users,
)
