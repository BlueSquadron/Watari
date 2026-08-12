"""Initial schema: all core tables, constraints, indexes, and next_case_number function.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "custom_fields_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "is_service_account",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("api_key_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "inactivity_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        sa.CheckConstraint(
            "role IN ('platform_admin', 'tenant_admin', 'analyst', "
            "'read_only', 'api_service_account')",
            name="ck_users_role",
        ),
    )

    # --- case_templates ---
    op.create_table(
        "case_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_severity", sa.String(length=50), nullable=True),
        sa.Column(
            "default_tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tasks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- cases ---
    op.create_table(
        "cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="new"
        ),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "merged_from",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["case_templates.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "case_number", name="uq_cases_tenant_case_number"
        ),
        sa.CheckConstraint(
            "status IN ('new', 'in_progress', 'pending', 'resolved', 'closed')",
            name="ck_cases_status",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'informational')",
            name="ck_cases_severity",
        ),
        sa.CheckConstraint(
            "outcome IN ('true_positive', 'false_positive', "
            "'indeterminate', 'not_applicable')",
            name="ck_cases_outcome",
        ),
    )

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="todo"
        ),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'done', 'cancelled')",
            name="ck_tasks_status",
        ),
    )

    # --- observables ---
    op.create_table(
        "observables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("tlp", sa.String(length=20), nullable=True),
        sa.Column(
            "is_ioc", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "type IN ('ip', 'domain', 'hostname', 'url', 'hash_md5', 'hash_sha1', "
            "'hash_sha256', 'email', 'filename', 'registry_key')",
            name="ck_observables_type",
        ),
        sa.CheckConstraint(
            "tlp IN ('red', 'amber', 'green', 'clear')",
            name="ck_observables_tlp",
        ),
    )
    op.create_index(
        "idx_observables_tenant_value",
        "observables",
        ["tenant_id", "value"],
    )
    op.create_index(
        "idx_observables_type_value",
        "observables",
        ["tenant_id", "type", "value"],
    )

    # --- assets ---
    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column(
            "is_compromised",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "custom_attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "name", name="uq_assets_case_name"),
        sa.CheckConstraint(
            "type IN ('workstation', 'server', 'network_device', 'mobile_device', "
            "'cloud_resource', 'other')",
            name="ck_assets_type",
        ),
    )

    # --- evidence ---
    op.create_table(
        "evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=True),
        sa.Column(
            "is_uploaded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_encrypted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("integrity_verified", sa.Boolean(), nullable=True),
        sa.Column(
            "integrity_mismatch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("registered_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["registered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "type IN ('disk_image', 'memory_dump', 'log_export', 'pcap', "
            "'document', 'other')",
            name="ck_evidence_type",
        ),
    )

    # --- timeline_entries ---
    op.create_table(
        "timeline_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_automatic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_timeline_case_timestamp",
        "timeline_entries",
        ["case_id", "event_timestamp"],
    )

    # --- timeline_asset_links (junction) ---
    op.create_table(
        "timeline_asset_links",
        sa.Column(
            "timeline_entry_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["timeline_entry_id"], ["timeline_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("timeline_entry_id", "asset_id"),
    )

    # --- note_folders ---
    op.create_table(
        "note_folders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["note_folders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- notes ---
    op.create_table(
        "notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["note_folders.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- alerts (OCSF 1.8.0 Detection Finding envelope + workflow) ---
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Denormalized OCSF fields — indexed for fast listing/filtering
        sa.Column("severity_id", sa.Integer(), nullable=False),
        sa.Column("source_product", sa.String(length=255), nullable=False),
        sa.Column("finding_uid", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        # Full OCSF Detection Finding document
        sa.Column(
            "ocsf_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Watari workflow state
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("dismiss_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "promoted_to_case_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("dedup_key", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["promoted_to_case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'promoted', 'dismissed')",
            name="ck_alerts_status",
        ),
    )
    op.create_index(
        "idx_alerts_dedup",
        "alerts",
        ["tenant_id", "dedup_key"],
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )
    op.create_index(
        "idx_alerts_tenant_status",
        "alerts",
        ["tenant_id", "status"],
    )
    op.create_index(
        "idx_alerts_tenant_severity_id",
        "alerts",
        ["tenant_id", "severity_id"],
    )

    # --- enrichment_sources ---
    op.create_table(
        "enrichment_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "supported_observable_types",
            postgresql.ARRAY(sa.String()),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- enrichment_results ---
    op.create_table(
        "enrichment_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "queried_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["observable_id"], ["observables.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["enrichment_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('success', 'error', 'timeout')",
            name="ck_enrichment_results_status",
        ),
    )

    # --- attack_reference ---
    op.create_table(
        "attack_reference",
        sa.Column("technique_id", sa.String(length=20), nullable=False),
        sa.Column("tactic_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_subtechnique",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("parent_technique_id", sa.String(length=20), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("technique_id"),
    )

    # --- attack_mappings ---
    op.create_table(
        "attack_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "timeline_entry_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("tactic_id", sa.String(length=20), nullable=False),
        sa.Column("technique_id", sa.String(length=20), nullable=False),
        sa.Column("sub_technique_id", sa.String(length=20), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["observable_id"], ["observables.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["timeline_entry_id"], ["timeline_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "case_id IS NOT NULL OR observable_id IS NOT NULL "
            "OR timeline_entry_id IS NOT NULL",
            name="ck_attack_mappings_at_least_one_ref",
        ),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "is_service_account",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX idx_audit_tenant_time ON audit_logs "
        "(tenant_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_audit_user ON audit_logs (user_id, created_at DESC)"
    )

    # --- modules ---
    op.create_table(
        "modules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "config_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("entry_point", sa.String(length=500), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "supported_evidence_types",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "subscribed_events",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint(
            "type IN ('pipeline', 'processor')", name="ck_modules_type"
        ),
    )

    # --- module_executions ---
    op.create_table(
        "module_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("trigger_event", sa.String(length=100), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "result", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_module_executions_status",
        ),
    )

    # --- report_templates ---
    op.create_table(
        "report_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("template_content", sa.Text(), nullable=False),
        sa.Column(
            "tag_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "type IN ('investigation', 'activity')",
            name="ck_report_templates_type",
        ),
        sa.CheckConstraint(
            "format IN ('docx', 'markdown', 'html')",
            name="ck_report_templates_format",
        ),
    )

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=True),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["report_templates.id"]),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- next_case_number function ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION next_case_number(p_tenant_id UUID)
        RETURNS INTEGER AS $$
        DECLARE
            next_num INTEGER;
        BEGIN
            SELECT COALESCE(MAX(case_number), 0) + 1 INTO next_num
            FROM cases WHERE tenant_id = p_tenant_id;
            RETURN next_num;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS next_case_number(UUID)")

    # Drop tables in reverse dependency order
    op.drop_table("reports")
    op.drop_table("report_templates")
    op.drop_table("module_executions")
    op.drop_table("modules")
    op.execute("DROP INDEX IF EXISTS idx_audit_user")
    op.execute("DROP INDEX IF EXISTS idx_audit_tenant_time")
    op.drop_table("audit_logs")
    op.drop_table("attack_mappings")
    op.drop_table("attack_reference")
    op.drop_table("enrichment_results")
    op.drop_table("enrichment_sources")
    op.drop_index("idx_alerts_tenant_severity_id", table_name="alerts")
    op.drop_index("idx_alerts_tenant_status", table_name="alerts")
    op.drop_index("idx_alerts_dedup", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("notes")
    op.drop_table("note_folders")
    op.drop_table("timeline_asset_links")
    op.drop_index("idx_timeline_case_timestamp", table_name="timeline_entries")
    op.drop_table("timeline_entries")
    op.drop_table("evidence")
    op.drop_table("assets")
    op.drop_index("idx_observables_type_value", table_name="observables")
    op.drop_index("idx_observables_tenant_value", table_name="observables")
    op.drop_table("observables")
    op.drop_table("tasks")
    op.drop_table("cases")
    op.drop_table("case_templates")
    op.drop_table("users")
    op.drop_table("tenants")

    # Drop extensions last
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
