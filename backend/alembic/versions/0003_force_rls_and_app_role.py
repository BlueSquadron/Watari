"""Force Row-Level Security and add a non-superuser application role.

The policies created in 0002 were never enforced. Three things prevented it,
and all three have to change together:

  1. The application connected as the `POSTGRES_USER` role, which the Postgres
     entrypoint always creates as a SUPERUSER. Superusers bypass RLS
     unconditionally. This migration creates a separate, unprivileged role for
     the request path.
  2. The tables were `ENABLE ROW LEVEL SECURITY`, which exempts the table
     owner — and migrations run as the owner, so the owner is also the role the
     app used. `FORCE` is what subjects the owner to its own policies.
  3. The tenant context the policies read was never set on any request. That
     part is fixed in the application layer (`src/auth/dependencies.py`).

A fourth fault only becomes reachable once the policies actually run. They
cast the session setting directly:

    tenant_id = current_setting('app.current_tenant', true)::UUID

`set_config(..., is_local => true)` is transaction-scoped, and when that
transaction ends the setting does not revert to NULL — it reverts to the empty
string. On a pooled connection the next transaction therefore evaluates
`''::UUID`, which raises `invalid input syntax for type uuid: ""` rather than
simply matching no rows. The policies are recreated below with `NULLIF`, so an
absent context yields NULL and the row is filtered — failing closed, which is
the whole point.

The owner role keeps its superuser status and is still used for migrations,
seeding, and the background worker, via `ADMIN_DATABASE_URL`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14 00:00:00.000000

"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Must match 0002. Tables with a NOT NULL tenant_id.
TABLES_STANDARD = [
    "users",
    "cases",
    "tasks",
    "observables",
    "assets",
    "evidence",
    "timeline_entries",
    "note_folders",
    "notes",
    "alerts",
    "enrichment_sources",
    "enrichment_results",
    "attack_mappings",
    "audit_logs",
    "module_executions",
    "reports",
]

# Tables where tenant_id may be NULL (platform-wide / shared entries).
TABLES_NULLABLE_TENANT = ["case_templates", "report_templates"]

TABLES = TABLES_STANDARD + TABLES_NULLABLE_TENANT

# An absent context reads back as '' on a pooled connection, not NULL, so
# NULLIF has to come before the cast or the policy raises instead of filtering.
_TENANT = "NULLIF(current_setting('app.current_tenant', true), '')::UUID"
_IS_ADMIN = (
    "NULLIF(current_setting('app.is_platform_admin', true), '')::BOOLEAN IS TRUE"
)

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _app_role() -> tuple[str, str]:
    """Read the application role name and password from the environment."""
    name = os.getenv("APP_DB_USER", "watari_app")
    password = os.getenv("APP_DB_PASSWORD", "watari_app_dev_password")
    if not _IDENT.match(name):
        raise ValueError(
            f"APP_DB_USER {name!r} is not a plain SQL identifier. Role names are "
            "interpolated into DDL, which cannot take bind parameters."
        )
    return name, password


def upgrade() -> None:
    conn = op.get_bind()
    role, password = _app_role()

    # --- 1. The unprivileged application role -------------------------------
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
    ).scalar()

    # Passwords cannot be bound: CREATE/ALTER ROLE are utility statements.
    # Escape the literal by doubling quotes; the role name is validated above.
    quoted_password = "'" + password.replace("'", "''") + "'"

    if not exists:
        conn.exec_driver_sql(
            f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS "
            f"PASSWORD {quoted_password}"
        )
    else:
        # Idempotent: make sure an existing role has the privileges we assume.
        conn.exec_driver_sql(
            f"ALTER ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS "
            f"PASSWORD {quoted_password}"
        )

    conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    conn.exec_driver_sql(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
    )
    conn.exec_driver_sql(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
    )
    conn.exec_driver_sql(
        f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {role}"
    )
    # Tables created by later migrations must be reachable too.
    conn.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}"
    )
    conn.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {role}"
    )

    # --- 2. Recreate the policies so an absent context filters, not raises ---
    for table in TABLES_STANDARD:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = {_TENANT})"
        )
    for table in TABLES_NULLABLE_TENANT:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id IS NULL OR tenant_id = {_TENANT})"
        )
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS platform_admin_bypass ON {table}")
        op.execute(
            f"CREATE POLICY platform_admin_bypass ON {table} USING ({_IS_ADMIN})"
        )

    # --- 3. Subject the owner to the policies as well ------------------------
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    # Restore 0002's policy expressions verbatim.
    for table in TABLES_STANDARD:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )
    for table in TABLES_NULLABLE_TENANT:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING ("
            "tenant_id IS NULL "
            "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS platform_admin_bypass ON {table}")
        op.execute(
            f"CREATE POLICY platform_admin_bypass ON {table} "
            "USING (current_setting('app.is_platform_admin', true)::BOOLEAN = true)"
        )

    # The role is intentionally left in place. Dropping it would fail while any
    # object still depends on it, and re-creating it is cheap; revoking is the
    # reversible part.
    conn = op.get_bind()
    role, _ = _app_role()
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
    ).scalar()
    if exists:
        conn.exec_driver_sql(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {role}"
        )
        conn.exec_driver_sql(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE USAGE, SELECT ON SEQUENCES FROM {role}"
        )
        conn.exec_driver_sql(
            f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"
        )
        conn.exec_driver_sql(
            f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}"
        )
        conn.exec_driver_sql(
            f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {role}"
        )
        conn.exec_driver_sql(f"REVOKE USAGE ON SCHEMA public FROM {role}")
