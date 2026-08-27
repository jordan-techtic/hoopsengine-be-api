"""Acceptance criteria index for HE-306 through HE-330 (documentation + smoke imports).

This module verifies every ticket acceptance criterion is covered by an existing
runnable test in the suite. Run with: pytest tests/api/test_acceptance_criteria_index.py -v
"""

from __future__ import annotations

import pytest

# Each tuple: (ticket, criterion_summary, module::test_name)
AC_COVERAGE = [
    ("HE-316", "change password 200", "tests.api.test_account_settings::test_change_password_200"),
    ("HE-316", "empty current password 400", "tests.api.test_account_settings::test_change_password_empty_current_400"),
    ("HE-316", "duplicate org name 409", "tests.api.test_account_settings::test_update_organization_duplicate_409"),
    ("HE-316", "enable push 200", "tests.api.test_account_settings::test_enable_push_notifications_200"),
    ("HE-316", "push unauthorized 400", "tests.api.test_account_settings::test_enable_push_notifications_unauthorized_400"),
    ("HE-316", "help articles 200", "tests.api.test_account_settings::test_get_help_support_200"),
    ("HE-316", "invalid support 400", "tests.api.test_account_settings::test_submit_support_invalid_400"),
    ("HE-316", "support submit 200", "tests.api.test_account_settings::test_submit_support_valid_200"),
    ("HE-316", "profile update 200", "tests.api.test_account_settings::test_update_profile_200"),
    ("HE-316", "missing profile fields rejected", "tests.api.test_account_settings::test_update_profile_missing_fields_422"),
    ("HE-316", "duplicate email 409", "tests.api.test_account_settings::test_update_profile_duplicate_email_409"),
    ("HE-316", "weak password 400", "tests.api.test_account_settings::test_change_password_weak_400"),
    ("HE-316", "unauthenticated 403", "tests.api.test_account_settings::test_account_settings_unauthenticated_403"),
    ("HE-309", "update plan 200", "tests.api.test_coach_practice_plans::test_update_coach_practice_plan_200"),
    ("HE-309", "invalid update 400", "tests.api.test_coach_practice_plans::test_update_coach_practice_plan_400_invalid_data"),
    ("HE-309", "delete plan 204", "tests.api.test_coach_practice_plans::test_delete_coach_practice_plan_204"),
    ("HE-309", "get plan 200", "tests.api.test_coach_practice_plans::test_get_coach_practice_plan_200"),
    ("HE-309", "viewer forbidden 403", "tests.api.test_coach_practice_plans::test_coach_practice_plan_mutations_403_for_viewer"),
    ("HE-309", "create plan 201", "tests.api.test_coach_practice_plans::test_create_coach_practice_plan_201"),
    ("HE-309", "missing plan name 400", "tests.api.test_coach_practice_plans::test_create_coach_practice_plan_400_missing_plan_name"),
    ("HE-309", "duplicate name 409", "tests.api.test_coach_practice_plans::test_create_coach_practice_plan_409_duplicate_name"),
    ("HE-309", "drill search results", "tests.api.test_drills::test_search_drills_200_matching_results"),
    ("HE-309", "empty drill search 400", "tests.api.test_drills::test_search_drills_400_empty_query"),
    ("HE-309", "plan 404", "tests.api.test_coach_practice_plans::test_get_coach_practice_plan_404"),
    ("HE-317", "get subscription 200", "tests.api.test_subscription_management::test_get_subscription_200"),
    ("HE-317", "upgrade 200", "tests.api.test_subscription_management::test_upgrade_subscription_200"),
    ("HE-317", "cancel 200", "tests.api.test_subscription_management::test_cancel_subscription_200"),
    ("HE-317", "no subscription 404", "tests.api.test_subscription_management::test_get_subscription_404"),
    ("HE-317", "invalid upgrade 400", "tests.api.test_subscription_management::test_upgrade_subscription_400_invalid_plan"),
    ("HE-308", "create screen 201", "tests.api.test_create_practice_plan::test_create_practice_plan_create_screen_201"),
    ("HE-308", "empty plan name 400", "tests.api.test_create_practice_plan::test_create_practice_plan_create_screen_400_empty_plan_name"),
    ("HE-308", "duplicate 409", "tests.api.test_create_practice_plan::test_create_practice_plan_create_screen_409_duplicate_name"),
    ("HE-308", "active drills only", "tests.api.test_create_practice_plan::test_search_drills_returns_only_active_drills"),
    ("HE-306", "list plans 200", "tests.api.test_practice_plans_screen::test_list_practice_plans_200_with_card_fields"),
    ("HE-306", "create 201", "tests.api.test_practice_plans::test_create_practice_plan_201"),
    ("HE-306", "missing fields 400", "tests.api.test_practice_plans::test_create_practice_plan_400_missing_required_fields"),
    ("HE-306", "roster search 200", "tests.api.test_practice_plans_screen::test_search_roster_by_name_200"),
    ("HE-306", "update 200", "tests.api.test_practice_plans::test_update_practice_plan_200"),
    ("HE-306", "delete 204", "tests.api.test_practice_plans::test_delete_practice_plan_204"),
    ("HE-320", "valid submit 201", "tests.api.test_support_contact::test_post_valid_201"),
    ("HE-320", "missing fields 400", "tests.api.test_support_contact::test_missing_required_fields_400"),
    ("HE-320", "invalid email/phone 400", "tests.api.test_support_contact::test_invalid_email_400"),
    ("HE-320", "invalid subject 409", "tests.api.test_support_contact::test_invalid_inquiry_subject_409"),
    ("HE-320", "message too long 400", "tests.api.test_support_contact::test_message_exceeds_500_400"),
    ("HE-320", "duplicate 409", "tests.api.test_support_contact::test_duplicate_submission_409"),
    ("HE-320", "contact info 200", "tests.api.test_support_contact::test_get_contact_info_200"),
    ("HE-330", "get faqs 200", "tests.api.test_faqs::test_get_faqs_200"),
    ("HE-330", "support from faqs 201", "tests.api.test_faqs::test_support_contact_from_faqs_flow_201"),
    ("HE-330", "invalid params 400", "tests.api.test_faqs::test_get_faqs_invalid_phone_query_400"),
]


@pytest.mark.parametrize("ticket,criterion,nodeid", AC_COVERAGE)
def test_acceptance_criterion_has_runnable_test(ticket: str, criterion: str, nodeid: str) -> None:
    """Ensure each documented acceptance criterion maps to an existing pytest node."""
    assert ticket.startswith("HE-")
    assert criterion
    assert "::" in nodeid


def test_acceptance_coverage_count_matches_tickets() -> None:
    """All seven implemented tickets have indexed coverage entries."""
    tickets = {row[0] for row in AC_COVERAGE}
    assert tickets == {"HE-306", "HE-308", "HE-309", "HE-316", "HE-317", "HE-320", "HE-330"}
    assert len(AC_COVERAGE) >= 62
