import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.tables import (
    STRIPE_SUBSCRIPTIONS_TABLE,
    SUBSCRIPTION_PLANS_TABLE,
    SUPPORT_REQUESTS_TABLE,
)

logger = logging.getLogger(__name__)


async def _table_exists(connection: AsyncConnection, table_name: str) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
    )


async def _column_exists(
    connection: AsyncConnection,
    *,
    table_name: str,
    column_name: str,
) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND column_name = :column_name
                )
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
    )


async def _constraint_exists(
    connection: AsyncConnection,
    *,
    table_name: str,
    constraint_name: str,
) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND constraint_name = :constraint_name
                )
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        )
    )


async def migrate_subscription_plans_role_column(connection: AsyncConnection) -> None:
    if not await _table_exists(connection, SUBSCRIPTION_PLANS_TABLE):
        return

    has_plan_for = await _column_exists(
        connection,
        table_name=SUBSCRIPTION_PLANS_TABLE,
        column_name="plan_for",
    )
    has_role = await _column_exists(
        connection,
        table_name=SUBSCRIPTION_PLANS_TABLE,
        column_name="role",
    )

    if has_plan_for and not has_role:
        await connection.execute(
            text(
                f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} "
                "RENAME COLUMN plan_for TO role"
            )
        )
        await connection.execute(
            text(
                f"UPDATE {SUBSCRIPTION_PLANS_TABLE} "
                "SET role = 'org_admin' WHERE role = 'organization'"
            )
        )
        logger.info("Renamed subscription_plans_staging.plan_for to role")

    elif has_plan_for and has_role:
        await connection.execute(
            text(
                f"UPDATE {SUBSCRIPTION_PLANS_TABLE} "
                "SET role = CASE "
                "WHEN plan_for = 'organization' THEN 'org_admin' "
                "ELSE plan_for END "
                "WHERE role IS NULL OR role = ''"
            )
        )
        await connection.execute(
            text(f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} DROP COLUMN plan_for")
        )
        logger.info("Migrated plan_for values into role and dropped plan_for column")

    await _replace_plan_for_check_constraint(connection)


async def _replace_plan_for_check_constraint(connection: AsyncConnection) -> None:
    old_constraint = f"{SUBSCRIPTION_PLANS_TABLE}_plan_for_check"
    new_constraint = f"{SUBSCRIPTION_PLANS_TABLE}_role_check"

    if await _constraint_exists(
        connection,
        table_name=SUBSCRIPTION_PLANS_TABLE,
        constraint_name=old_constraint,
    ):
        await connection.execute(
            text(f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} DROP CONSTRAINT {old_constraint}")
        )
        logger.info("Dropped legacy check constraint %s", old_constraint)

    if not await _constraint_exists(
        connection,
        table_name=SUBSCRIPTION_PLANS_TABLE,
        constraint_name=new_constraint,
    ):
        await connection.execute(
            text(
                f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} "
                f"ADD CONSTRAINT {new_constraint} "
                "CHECK (role IN ('org_admin', 'coach'))"
            )
        )
        logger.info("Added check constraint %s", new_constraint)


async def migrate_legacy_subscriptions_table(connection: AsyncConnection) -> None:
    legacy_table = "subscriptions_staging"
    if legacy_table == STRIPE_SUBSCRIPTIONS_TABLE:
        return

    if not await _table_exists(connection, legacy_table):
        return

    if await _table_exists(connection, STRIPE_SUBSCRIPTIONS_TABLE):
        legacy_count = await connection.scalar(text(f"SELECT COUNT(*) FROM {legacy_table}")) or 0
        if legacy_count == 0:
            await connection.execute(text(f"DROP TABLE {legacy_table}"))
            logger.info("Dropped empty legacy table %s", legacy_table)
        else:
            logger.warning(
                "Legacy table %s has data and %s already exists; manual migration required",
                legacy_table,
                STRIPE_SUBSCRIPTIONS_TABLE,
            )
        return

    await connection.execute(
        text(f"ALTER TABLE {legacy_table} RENAME TO {STRIPE_SUBSCRIPTIONS_TABLE}")
    )
    logger.info("Renamed %s to %s", legacy_table, STRIPE_SUBSCRIPTIONS_TABLE)


async def migrate_plan_archive_columns(connection: AsyncConnection) -> None:
    if await _table_exists(connection, SUBSCRIPTION_PLANS_TABLE):
        if not await _column_exists(
            connection,
            table_name=SUBSCRIPTION_PLANS_TABLE,
            column_name="archived_at",
        ):
            await connection.execute(
                text(
                    f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} "
                    "ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE NULL"
                )
            )
            logger.info("Added archived_at to %s", SUBSCRIPTION_PLANS_TABLE)
        if not await _column_exists(
            connection,
            table_name=SUBSCRIPTION_PLANS_TABLE,
            column_name="replacement_plan_id",
        ):
            await connection.execute(
                text(
                    f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} "
                    "ADD COLUMN replacement_plan_id UUID NULL"
                )
            )
            logger.info("Added replacement_plan_id to %s", SUBSCRIPTION_PLANS_TABLE)

    if await _table_exists(connection, STRIPE_SUBSCRIPTIONS_TABLE):
        if not await _column_exists(
            connection,
            table_name=STRIPE_SUBSCRIPTIONS_TABLE,
            column_name="pending_plan_id",
        ):
            await connection.execute(
                text(
                    f"ALTER TABLE {STRIPE_SUBSCRIPTIONS_TABLE} "
                    "ADD COLUMN pending_plan_id UUID NULL"
                )
            )
            logger.info("Added pending_plan_id to %s", STRIPE_SUBSCRIPTIONS_TABLE)


async def migrate_offline_sync_column(connection: AsyncConnection) -> None:
    """Add include_offline_sync boolean column to subscription plans table if missing."""
    if not await _table_exists(connection, SUBSCRIPTION_PLANS_TABLE):
        return

    if not await _column_exists(
        connection,
        table_name=SUBSCRIPTION_PLANS_TABLE,
        column_name="include_offline_sync",
    ):
        await connection.execute(
            text(
                f"ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} "
                "ADD COLUMN include_offline_sync BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        logger.info("Added include_offline_sync to %s", SUBSCRIPTION_PLANS_TABLE)


async def migrate_users_staging_to_users(connection: AsyncConnection) -> None:
    """
    Rename legacy `users_staging` → `users` on our owned DB.

    Safe for:
    - already renamed (`users` exists, `users_staging` gone)
    - fresh DBs (neither exists yet — create_managed_tables will create `users`)
    """
    legacy = "users_staging"
    current = "users"

    has_legacy = await _table_exists(connection, legacy)
    has_current = await _table_exists(connection, current)

    if has_current and not has_legacy:
        return

    if has_current and has_legacy:
        legacy_count = await connection.scalar(text(f'SELECT COUNT(*) FROM "{legacy}"')) or 0
        if legacy_count == 0:
            await connection.execute(text(f'DROP TABLE "{legacy}"'))
            logger.info("Dropped empty legacy table %s", legacy)
            return
        logger.warning(
            "Both %s and %s exist with data; leaving both in place — resolve manually",
            legacy,
            current,
        )
        return

    if not has_legacy:
        return

    await connection.execute(text(f'ALTER TABLE "{legacy}" RENAME TO "{current}"'))
    logger.info("Renamed %s to %s", legacy, current)

    rename_ops = [
        (
            f'ALTER TABLE "{current}" RENAME CONSTRAINT users_staging_pkey TO users_pkey',
            "users_staging_pkey",
        ),
        (
            f'ALTER TABLE "{current}" RENAME CONSTRAINT users_he_pkey TO users_pkey',
            "users_he_pkey",
        ),
        (
            f'ALTER TABLE "{current}" '
            "RENAME CONSTRAINT users_staging_role_check TO users_role_check",
            "users_staging_role_check",
        ),
        (
            f'ALTER TABLE "{current}" '
            "RENAME CONSTRAINT users_he_role_check TO users_role_check",
            "users_he_role_check",
        ),
        (
            "ALTER INDEX ix_users_staging_email RENAME TO ix_users_email",
            "ix_users_staging_email",
        ),
        (
            "ALTER INDEX ix_users_staging_role RENAME TO ix_users_role",
            "ix_users_staging_role",
        ),
        (
            "ALTER INDEX ix_users_staging_org_id RENAME TO ix_users_org_id",
            "ix_users_staging_org_id",
        ),
        (
            "ALTER INDEX ix_users_he_email RENAME TO ix_users_email",
            "ix_users_he_email",
        ),
        (
            "ALTER INDEX ix_users_he_role RENAME TO ix_users_role",
            "ix_users_he_role",
        ),
        (
            "ALTER INDEX ix_users_he_org_id RENAME TO ix_users_org_id",
            "ix_users_he_org_id",
        ),
    ]
    for statement, _name in rename_ops:
        # Failed DDL aborts the PG transaction; isolate each attempt with a savepoint.
        await connection.execute(text("SAVEPOINT users_rename_op"))
        try:
            await connection.execute(text(statement))
            await connection.execute(text("RELEASE SAVEPOINT users_rename_op"))
        except Exception:
            await connection.execute(text("ROLLBACK TO SAVEPOINT users_rename_op"))
            logger.debug("Skipped rename op: %s", statement)


async def migrate_support_request_phone_column(connection: AsyncConnection) -> None:
    """Add phone to support_requests when the table predates the column."""
    if not await _table_exists(connection, SUPPORT_REQUESTS_TABLE):
        return

    if not await _column_exists(
        connection,
        table_name=SUPPORT_REQUESTS_TABLE,
        column_name="phone",
    ):
        await connection.execute(
            text(
                f"ALTER TABLE {SUPPORT_REQUESTS_TABLE} "
                "ADD COLUMN phone VARCHAR(32) NULL"
            )
        )
        logger.info("Added phone to %s", SUPPORT_REQUESTS_TABLE)


async def migrate_organization_contact_columns(connection: AsyncConnection) -> None:
    """Add phone_number and address to client-domain organizations if missing."""
    if not await _table_exists(connection, "organizations"):
        return

    if not await _column_exists(
        connection,
        table_name="organizations",
        column_name="phone_number",
    ):
        await connection.execute(
            text("ALTER TABLE organizations ADD COLUMN phone_number TEXT NULL")
        )
        logger.info("Added phone_number to organizations")

    if not await _column_exists(
        connection,
        table_name="organizations",
        column_name="address",
    ):
        await connection.execute(
            text("ALTER TABLE organizations ADD COLUMN address TEXT NULL")
        )
        logger.info("Added address to organizations")


async def migrate_drill_submissions_player_submitter_column(
    connection: AsyncConnection,
) -> None:
    """Add submitted_by_player_id to client-domain drill_submissions when missing."""
    if not await _table_exists(connection, "drill_submissions"):
        return

    if not await _column_exists(
        connection,
        table_name="drill_submissions",
        column_name="submitted_by_player_id",
    ):
        await connection.execute(
            text(
                "ALTER TABLE drill_submissions "
                "ADD COLUMN submitted_by_player_id UUID NULL "
                "REFERENCES players(id)"
            )
        )
        logger.info("Added submitted_by_player_id to drill_submissions")


async def run_subscription_schema_migrations(connection: AsyncConnection) -> None:
    await migrate_users_staging_to_users(connection)
    await migrate_subscription_plans_role_column(connection)
    await migrate_legacy_subscriptions_table(connection)
    await migrate_plan_archive_columns(connection)
    await migrate_offline_sync_column(connection)
    await migrate_organization_contact_columns(connection)
    await migrate_support_request_phone_column(connection)
    await migrate_drill_submissions_player_submitter_column(connection)
