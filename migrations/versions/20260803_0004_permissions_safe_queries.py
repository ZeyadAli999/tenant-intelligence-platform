"""Add tenant-safe permissions and query execution traces.

Revision ID: 20260803_0004
Revises: 20260803_0003
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0004"
down_revision: str | None = "20260803_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_database_tables_id_connection_tenant",
        "database_tables",
        ["id", "connection_id", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_database_columns_id_table_tenant",
        "database_columns",
        ["id", "table_id", "tenant_id"],
    )
    op.create_table(
        "table_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_insert", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_update", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_delete", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "row_filter",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role_id IS NOT NULL AND user_id IS NULL) OR "
            "(role_id IS NULL AND user_id IS NOT NULL)",
            name="chk_table_permissions_subject_exactly_one",
        ),
        sa.CheckConstraint(
            "NOT can_insert AND NOT can_update AND NOT can_delete",
            name="chk_table_permissions_chat_read_only",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["roles.id", "roles.tenant_id"],
            name="fk_table_permissions_role_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_table_permissions_user_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_table_permissions_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["table_id", "connection_id", "tenant_id"],
            [
                "database_tables.id",
                "database_tables.connection_id",
                "database_tables.tenant_id",
            ],
            name="fk_table_permissions_table_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "table_id", "tenant_id", name="uq_table_permissions_id_table_tenant"
        ),
    )
    op.create_index(
        "idx_table_permissions_tenant_connection",
        "table_permissions",
        ["tenant_id", "connection_id"],
    )
    op.create_index(
        "uq_table_permissions_user_table",
        "table_permissions",
        ["user_id", "table_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_table_permissions_role_table",
        "table_permissions",
        ["role_id", "table_id"],
        unique=True,
        postgresql_where=sa.text("role_id IS NOT NULL"),
    )
    op.create_table(
        "column_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("column_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_filter", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("can_aggregate", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("mask_type", sa.String(50), nullable=True),
        sa.CheckConstraint(
            "mask_type IS NULL OR mask_type IN ('redact', 'partial', 'hash', 'null')",
            name="chk_column_permissions_mask_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["table_permission_id", "table_id", "tenant_id"],
            [
                "table_permissions.id",
                "table_permissions.table_id",
                "table_permissions.tenant_id",
            ],
            name="fk_column_permissions_table_permission_scope",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["column_id", "table_id", "tenant_id"],
            [
                "database_columns.id",
                "database_columns.table_id",
                "database_columns.tenant_id",
            ],
            name="fk_column_permissions_column_table_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "table_permission_id",
            "column_id",
            name="uq_column_permissions_permission_column",
        ),
    )
    op.create_index(
        "idx_column_permissions_tenant_table",
        "column_permissions",
        ["tenant_id", "table_id"],
    )
    op.create_table(
        "query_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column("normalized_sql", sa.Text(), nullable=True),
        sa.Column("query_type", sa.String(30), nullable=True),
        sa.Column("validation_status", sa.String(30), nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "applied_row_filters",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "referenced_tables",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "referenced_columns",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("execution_status", sa.String(30), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("returned_row_count", sa.Integer(), nullable=True),
        sa.Column("result_preview", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "query_type IN ('select', 'with')",
            name="chk_query_executions_query_type_valid",
        ),
        sa.CheckConstraint(
            "validation_status IN ('accepted', 'rejected')",
            name="chk_query_executions_validation_status_valid",
        ),
        sa.CheckConstraint(
            "execution_status IS NULL OR execution_status IN "
            "('pending', 'succeeded', 'failed', 'timeout', 'rejected')",
            name="chk_query_executions_execution_status_valid",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_query_executions_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_query_executions_tenant_created",
        "query_executions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_query_executions_connection", "query_executions", ["connection_id"]
    )


def downgrade() -> None:
    op.drop_table("query_executions")
    op.drop_table("column_permissions")
    op.drop_table("table_permissions")
    op.drop_constraint(
        "uq_database_columns_id_table_tenant", "database_columns", type_="unique"
    )
    op.drop_constraint(
        "uq_database_tables_id_connection_tenant", "database_tables", type_="unique"
    )
