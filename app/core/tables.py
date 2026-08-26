MANAGED_TABLE_SUFFIX = "staging"


def managed_table_name(base_table: str) -> str:
    """Build a managed table name: `{base_table}_staging`."""
    return f"{base_table}_{MANAGED_TABLE_SUFFIX}"


# Canonical app users table (no _staging suffix — this is our owned DB).
USERS_TABLE = "users"

REVOKED_TOKENS_TABLE = managed_table_name("revoked_tokens")
SUPPORT_REQUESTS_TABLE = managed_table_name("support_requests")
SUBSCRIPTION_PLANS_TABLE = managed_table_name("subscription_plans")
STRIPE_SUBSCRIPTIONS_TABLE = managed_table_name("stripe_subscriptions")

# Tables created/owned by this API (not client domain SQL).
MANAGED_TABLE_NAMES = frozenset(
    {
        USERS_TABLE,
        REVOKED_TOKENS_TABLE,
        SUPPORT_REQUESTS_TABLE,
        SUBSCRIPTION_PLANS_TABLE,
        STRIPE_SUBSCRIPTIONS_TABLE,
    }
)
