# Migrating staging DB → Hoops Engine DB

This runbook moves **required** schema + data from `hoops-engine-db-staging`
(Supabase import on DigitalOcean) into a clean `hoops-engine-db`, without
touching the staging database.

## What gets created / copied

| Layer | Tables | How |
|---|---|---|
| Client domain schema | `organizations`, `teams`, `subteams`, `coaches`, `players`, `drills`, plans, sessions, `user_roles`, `usernames`, … | `docs/sql/hoops_engine_client_schema.sql` |
| App-managed schema | `users`, `subscription_plans_staging`, `stripe_subscriptions_staging`, `support_requests_staging`, `revoked_tokens_staging` | SQLAlchemy `create_managed_tables` |
| Default data copy | orgs, teams, drills, players, practice plans, user_roles, usernames, users, subscription_plans_staging, support_requests_staging, stripe_subscriptions_staging | `migrate_staging_data.py` |
| Not copied by default | `auth.*`, `revoked_tokens_staging`, empty coaches/subteams, `session_data` history | optional via `--include-optional` |

Auth no longer uses Supabase `auth.users`. Login uses `users`.

## Prerequisites

1. Target DB exists and is empty (or you accept `--replace` on selected tables).
2. `.env` `DATABASE_URL` points at the **target** (`hoops-engine-db`).
3. Staging DB stays available as **read-only** source.

## Steps

### 1. Bootstrap schema on target

```powershell
cd hoops-engine-backend
# DATABASE_URL already points at hoops-engine-db in .env
python scripts/bootstrap_hoops_engine_db.py
```

### 2. Copy required data (staging → target)

```powershell
$env:SOURCE_DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:5432/hoops-engine-db-staging"
# TARGET defaults to DATABASE_URL / TARGET_DATABASE_URL
python scripts/migrate_staging_data.py --dry-run
python scripts/migrate_staging_data.py
```

Optional history (session_data, etc.):

```powershell
python scripts/migrate_staging_data.py --include-optional
```

Re-run and overwrite target rows for selected tables:

```powershell
python scripts/migrate_staging_data.py --replace
```

### 3. Ensure superadmin (optional)

```powershell
python scripts/create_superadmin.py
```

### 4. Start API against target

```powershell
python -m app.main
```

Confirm login with an existing staging user (same password hashes in `users`).

## Safety guarantees

- Source DB is never truncated or altered by these scripts.
- App startup only auto-creates managed tables (`users` + other app tables; never a partial `organizations` table).
- Client tables must come from bootstrap SQL so FKs and columns stay correct.
- Staging environment can keep using `hoops-engine-db-staging` unchanged.

## Do not run on staging by mistake

`migrate_staging_data.py` refuses to run when source and target database names are the same.
Always set `SOURCE_DATABASE_URL` to `.../hoops-engine-db-staging` and target to `.../hoops-engine-db`.
