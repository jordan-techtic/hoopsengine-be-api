"""Cross-ticket org-admin module acceptance and gap tests (HE-400, HE-406, HE-408).

Covers acceptance criteria not mapped elsewhere: duplicate profile email (HE-406),
upgrade error messaging (HE-408), removal confirmation (HE-400), auth 401 guards,
and unicode edge cases. Reuses existing PostgreSQL fixtures from tests/conftest.py.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    ORG_ADMIN_PRACTICE_PLANS_BASE,
    ORG_ADMIN_REMOVE_PLAYERS_BASE,
    ORG_ADMIN_RESET_PASSWORD_BASE,
    ORG_ADMIN_SUBSCRIPTION_BASE,
    ORG_ADMIN_TEAMS_BASE,
    ORG_CHANGE_PASSWORD_BASE,
    ORGANIZATION_PROFILE_BASE,
    ORG_ADMIN_PLAYERS_BASE,
    PRACTICE_PLANS_BASE,
    REGULAR_EMAIL,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    TEST_NEW_SECURE_PASSWORD,
    TEST_VALID_PASSWORD,
    auth_headers,
    create_access_token,
    sync_engine,
)
from tests.fixtures.org_admin_module_users import seed_org_admin_user

ORG_MODULE_ADMIN_ID = UUID("00000000-0000-4000-8000-0000000000a1")
REMOVAL_PLAYER_ID = UUID("00000000-0000-4000-8000-000000000092")

VALID_PROFILE_PAYLOAD = {
    "organization_name": "Courtside Elite Academy",
    "address": "1234 Basketball Ave",
    "email": "org.module@test.com",
    "phone_number": "+1 (555) 382-9102",
    "first_name": "Module",
    "last_name": "Admin",
    "phone": "+1-555-0100",
}

VALID_REMOVAL_PAYLOAD = {
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "(555) 123-4567",
}


@pytest.fixture
def org_admin_module_headers(seeded_users: dict) -> dict[str, str]:
    """Org admin bearer token for cross-ticket acceptance tests."""
    return seed_org_admin_user(
        user_id=ORG_MODULE_ADMIN_ID,
        email="orgadmin.module@test.com",
        username="orgadminmodule",
    )


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure client practice plan tables exist."""


# --- HE-406 Account settings / profile ---


def test_he406_get_organization_profile_200(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    response = client.get(ORGANIZATION_PROFILE_BASE, headers=org_admin_module_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"] == str(SEEDED_ORG_ID)
    assert body["organization_name"]
    assert body["profile"]["email"]


def test_he406_update_organization_profile_200(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    response = client.put(
        ORGANIZATION_PROFILE_BASE,
        json=VALID_PROFILE_PAYLOAD,
        headers=org_admin_module_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "saved"
    assert body["organization_name"] == VALID_PROFILE_PAYLOAD["organization_name"]
    assert body["email"] == VALID_PROFILE_PAYLOAD["email"]


def test_he406_update_profile_duplicate_email_409(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
    seeded_users: dict,
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["email"] = REGULAR_EMAIL
    response = client.put(
        ORGANIZATION_PROFILE_BASE,
        json=payload,
        headers=org_admin_module_headers,
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_he406_update_profile_invalid_data_400(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    payload = dict(VALID_PROFILE_PAYLOAD)
    payload["organization_name"] = ""
    response = client.put(
        ORGANIZATION_PROFILE_BASE,
        json=payload,
        headers=org_admin_module_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_he406_change_password_missing_token_401(client: TestClient) -> None:
    response = client.post(
        ORG_CHANGE_PASSWORD_BASE,
        json={
            "current_password": TEST_VALID_PASSWORD,
            "new_password": TEST_NEW_SECURE_PASSWORD,
            "confirm_password": TEST_NEW_SECURE_PASSWORD,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


# --- HE-408 Subscription management ---


def test_he408_get_subscription_includes_notification(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    from tests.api.test_dashboard import _persist_plans_then_subscriptions, _truncate_subscription_tables
    from tests.api.test_org_admin_subscription import _org_admin_subscription, _org_basic_plan

    _truncate_subscription_tables()
    basic = _org_basic_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    subscription.subscriber_user_id = ORG_MODULE_ADMIN_ID
    subscription.subscriber_email = "orgadmin.module@test.com"
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.get(ORG_ADMIN_SUBSCRIPTION_BASE, headers=org_admin_module_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["notification"]
    assert body["subscription_plan"] == "Basic Plan"


def test_he408_upgrade_invalid_plan_error_message(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    from tests.api.test_dashboard import _persist_plans_then_subscriptions, _truncate_subscription_tables
    from tests.api.test_org_admin_subscription import _org_admin_subscription, _org_basic_plan

    _truncate_subscription_tables()
    basic = _org_basic_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    subscription.subscriber_user_id = ORG_MODULE_ADMIN_ID
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.post(
        f"{ORG_ADMIN_SUBSCRIPTION_BASE}/upgrade",
        headers=org_admin_module_headers,
        json={"plan_id": "00000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]


def test_he408_subscription_missing_token_401(client: TestClient) -> None:
    assert client.get(ORG_ADMIN_SUBSCRIPTION_BASE).status_code == 401


# --- HE-400 Remove player ---


@pytest.fixture
def seed_removal_player(org_admin_module_headers: dict[str, str]) -> None:
    from sqlalchemy import text

    with sync_engine.begin() as connection:
        for column, ddl in (
            ("email", "ALTER TABLE players ADD COLUMN email text"),
            ("phone", "ALTER TABLE players ADD COLUMN phone text"),
            ("team_id", "ALTER TABLE players ADD COLUMN team_id uuid"),
            ("active", "ALTER TABLE players ADD COLUMN active boolean DEFAULT true"),
        ):
            exists = connection.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'players'
                          AND column_name = :column
                    )
                    """
                ),
                {"column": column},
            ).scalar()
            if not exists:
                connection.execute(text(ddl))
        connection.execute(
            text(
                """
                INSERT INTO players (
                    id, org_id, first_name, last_name, email, phone, active
                ) VALUES (
                    :id, :org_id, 'Sarah', 'Jenkins',
                    'sarah.jenkins@school.edu', '(555) 123-4567', true
                )
                ON CONFLICT (id) DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    active = EXCLUDED.active
                """
            ),
            {"id": REMOVAL_PLAYER_ID, "org_id": SEEDED_ORG_ID},
        )


def test_he400_removal_confirmation_message_in_detail(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
    seed_removal_player: None,
) -> None:
    response = client.get(
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        headers=org_admin_module_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_message"] == REMOVAL_CONFIRMATION_MESSAGE
    assert body["full_name"] == "Sarah Jenkins"


def test_he400_remove_player_missing_token_401(
    client: TestClient,
    seed_removal_player: None,
) -> None:
    response = client.request(
        "DELETE",
        f"{ORG_ADMIN_REMOVE_PLAYERS_BASE}/{REMOVAL_PLAYER_ID}",
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 401


# --- Auth 401 guards for other org-admin modules ---


def test_he402_practice_plans_missing_token_401(client: TestClient) -> None:
    assert client.get(ORG_ADMIN_PRACTICE_PLANS_BASE).status_code == 401


def test_he380_teams_missing_token_401(client: TestClient) -> None:
    assert client.get(ORG_ADMIN_TEAMS_BASE).status_code == 401


def test_he383_assignments_list_missing_token_401(client: TestClient) -> None:
    assert client.get(PRACTICE_PLANS_BASE).status_code == 401


def test_he426_players_missing_token_401(client: TestClient) -> None:
    assert client.get(ORG_ADMIN_PLAYERS_BASE).status_code == 401


def test_he398_reset_password_missing_token_401(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_RESET_PASSWORD_BASE,
        json={
            "new_password": TEST_NEW_SECURE_PASSWORD,
            "confirm_password": TEST_NEW_SECURE_PASSWORD,
        },
    )
    assert response.status_code == 401


def test_he406_profile_missing_token_401(client: TestClient) -> None:
    assert client.get(ORGANIZATION_PROFILE_BASE).status_code == 401


# --- Edge cases ---


def test_he380_create_team_unicode_name_edge_case(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    response = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_module_headers,
        json={
            "team_name": "Varsity — Elite",
            "team_code": "VAR-UNI01",
            "team_description": "Unicode dash team name",
            "age_group": "U18",
            "full_name": "Module Admin",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert "—" in body["team_name"]


def test_he402_create_plan_empty_drill_description_edge(
    client: TestClient,
    org_admin_module_headers: dict[str, str],
) -> None:
    response = client.post(
        ORG_ADMIN_PRACTICE_PLANS_BASE,
        headers=org_admin_module_headers,
        json={
            "name": f"Edge Plan {ORG_MODULE_ADMIN_ID.hex[:8]}",
            "description": "Plan with optional empty drill description",
            "drills": [{"drill_name": "Warm Up", "drill_description": ""}],
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 201
    assert response.json()["drills"][0]["drill_name"] == "Warm Up"


def test_he426_players_forbidden_viewer_403(
    client: TestClient,
    seeded_users: dict,
) -> None:
    from tests.conftest import VIEWER_ID

    viewer_headers = auth_headers(create_access_token(VIEWER_ID))
    response = client.get(ORG_ADMIN_PLAYERS_BASE, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
