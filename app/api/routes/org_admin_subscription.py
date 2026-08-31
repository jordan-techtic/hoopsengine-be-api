# In org_admin_subscription.py VALIDATION_ERROR_RESPONSES replace single 400 with:
VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid subscription plan or upgrade request",
        examples={
            "invalid_plan": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": [{"field": "plan_id", "message": "Subscription plan is invalid or unavailable"}],
            },
            "upgrade_failed": {
                "code": "VALIDATION_ERROR",
                "message": "Unable to upgrade subscription",
                "details": [{"field": "full_name", "message": "Selected plan could not be applied"}],
            },
        },
    ),
    ...
}
# Extend upgrade description: "On failure, clients should display error.message; notification is only present on 200 success responses."