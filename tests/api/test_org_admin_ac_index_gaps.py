"""Acceptance criteria index entries for HE-400 and HE-406 gaps.

Append ORG_ADMIN_AC_GAP_COVERAGE to AC_COVERAGE in tests/api/test_acceptance_criteria_index.py.
"""

ORG_ADMIN_AC_GAP_COVERAGE = [
    ("HE-400", "remove player 200", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_200"),
    ("HE-400", "invalid phone 400", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_400_invalid_phone"),
    ("HE-400", "invalid email 400", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_400_invalid_email"),
    ("HE-400", "player not found 404", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_404_not_found"),
    ("HE-400", "confirmation message", "tests.api.test_org_admin_module_acceptance::test_he400_removal_confirmation_message_in_detail"),
    ("HE-400", "success message", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_200"),
    ("HE-400", "email already registered 409", "tests.api.test_org_admin_remove_player::test_remove_org_admin_player_409_email_already_registered"),
    ("HE-406", "get profile 200", "tests.api.test_org_admin_module_acceptance::test_he406_get_organization_profile_200"),
    ("HE-406", "update profile 200", "tests.api.test_org_admin_module_acceptance::test_he406_update_organization_profile_200"),
    ("HE-406", "invalid profile data 400", "tests.api.test_org_admin_module_acceptance::test_he406_update_profile_invalid_data_400"),
    ("HE-406", "duplicate email 409", "tests.api.test_org_admin_module_acceptance::test_he406_update_profile_duplicate_email_409"),
    ("HE-408", "upgrade error message", "tests.api.test_org_admin_module_acceptance::test_he408_upgrade_invalid_plan_error_message"),
]
