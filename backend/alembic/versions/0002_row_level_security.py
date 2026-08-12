"""Row-Level Security policies for tenant isolation.

Enables RLS on all tenant-scoped tables and creates tenant_isolation
and platform_admin_bypass policies.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:01.000000

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables with a NOT NULL tenant_id column — standard tenant isolation
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

# Tables where tenant_id can be NULL (platform-wide / shared entries)
TABLES_NULLABLE_TENANT = [
    "case_templates",
    "report_templates",
]


def upgrade() -> None:
    # Standard tenant-scoped tables
    for table in TABLES_STANDARD:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant', true)::UUID)
            """
        )
        op.execute(
            f"""
            CREATE POLICY platform_admin_bypass ON {table}
                USING (current_setting('app.is_platform_admin', true)::BOOLEAN = true)
            """
        )

    # Tables where tenant_id is nullable (platform-wide / shared)
    for table in TABLES_NULLABLE_TENANT:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (
                    tenant_id IS NULL
                    OR tenant_id = current_setting('app.current_tenant', true)::UUID
                )
            """
        )
        op.execute(
            f"""
            CREATE POLICY platform_admin_bypass ON {table}
                USING (current_setting('app.is_platform_admin', true)::BOOLEAN = true)
            """
        )


def downgrade() -> None:
    # Drop policies and disable RLS in reverse order
    for table in reversed(TABLES_NULLABLE_TENANT):
        op.execute(f"DROP POLICY IF EXISTS platform_admin_bypass ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in reversed(TABLES_STANDARD):
        op.execute(f"DROP POLICY IF EXISTS platform_admin_bypass ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
