NOTE: Use the existing tests/conftest.py in the repository. It already provides:
- PostgreSQL test DB via TEST_DATABASE_URL / DATABASE_URL from .env.test
- Session-scoped schema creation (Organization + app-managed tables)
- autouse mock_third_party_services patching SendGrid and Stripe
- Five seeded users: admin, user (regular), viewer (player), inactive, new
- Auth header fixtures: admin_headers, user_headers, viewer_headers, inactive_headers, expired_user_headers
- seed_player_drills fixture seeding subteams, subteam_drill_sets, players link, and practice_sessions cleanup
- Constants: PLAYER_DRILLS_BASE, PLAYER_START_BASE, DRILLS_BASE, SEEDED_PLAYER_DRILL_ONE_ID, SEEDED_PLAYER_DRILL_TWO_ID

No conftest changes are required for the generated player module tests.