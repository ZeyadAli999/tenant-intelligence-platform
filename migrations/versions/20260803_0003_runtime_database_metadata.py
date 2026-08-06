"""Add encrypted runtime database connections and metadata cache.

Revision ID: 20260803_0003
Revises: 20260803_0002
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0003"
down_revision: str | None = "20260803_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "database_connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("database_type", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column(
            "ssl_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "ssl_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "connection_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column(
            "schema_sync_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("last_schema_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(database_name) > 0",
            name=op.f("ck_database_connections_database_name_not_blank"),
        ),
        sa.CheckConstraint(
            "database_type = lower(trim(database_type))",
            name=op.f("ck_database_connections_database_type_normalized"),
        ),
        sa.CheckConstraint(
            "length(database_type) > 0",
            name=op.f("ck_database_connections_database_type_not_blank"),
        ),
        sa.CheckConstraint(
            "length(encrypted_password) > 0",
            name=op.f("ck_database_connections_encrypted_password_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(host)) > 0",
            name=op.f("ck_database_connections_host_not_blank"),
        ),
        sa.CheckConstraint(
            "name = lower(trim(name))",
            name=op.f("ck_database_connections_name_normalized"),
        ),
        sa.CheckConstraint(
            "length(name) > 0",
            name=op.f("ck_database_connections_name_not_blank"),
        ),
        sa.CheckConstraint(
            "port BETWEEN 1 AND 65535",
            name=op.f("ck_database_connections_port_valid"),
        ),
        sa.CheckConstraint(
            "schema_sync_status IN ('pending', 'running', 'succeeded', 'failed')",
            name=op.f("ck_database_connections_schema_sync_status_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'connected', 'failed')",
            name=op.f("ck_database_connections_status_valid"),
        ),
        sa.CheckConstraint(
            "length(trim(username)) > 0",
            name=op.f("ck_database_connections_username_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_database_connections_creator_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_database_connections_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_database_connections")),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_database_connections_id_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_database_connections_tenant_name",
        ),
    )
    op.create_index(
        "idx_database_connections_tenant",
        "database_connections",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "idx_database_connections_tenant_active",
        "database_connections",
        ["tenant_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "database_schemas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(schema_name) > 0",
            name=op.f("ck_database_schemas_schema_name_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_database_schemas_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_database_schemas")),
        sa.UniqueConstraint(
            "connection_id",
            "schema_name",
            name="uq_database_schemas_connection_name",
        ),
        sa.UniqueConstraint(
            "id",
            "connection_id",
            "tenant_id",
            name="uq_database_schemas_id_connection_tenant",
        ),
    )
    op.create_index(
        "idx_database_schemas_tenant_connection",
        "database_schemas",
        ["tenant_id", "connection_id"],
        unique=False,
    )

    op.create_table(
        "database_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_name", sa.String(length=255), nullable=False),
        sa.Column(
            "table_type",
            sa.String(length=50),
            server_default="table",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_row_count", sa.BigInteger(), nullable=True),
        sa.Column(
            "primary_key_columns",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_sensitive",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estimated_row_count IS NULL OR estimated_row_count >= 0",
            name=op.f("ck_database_tables_estimated_row_count_valid"),
        ),
        sa.CheckConstraint(
            "length(table_name) > 0",
            name=op.f("ck_database_tables_table_name_not_blank"),
        ),
        sa.CheckConstraint(
            "table_type IN ('table', 'view')",
            name=op.f("ck_database_tables_table_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_database_tables_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schema_id", "connection_id", "tenant_id"],
            [
                "database_schemas.id",
                "database_schemas.connection_id",
                "database_schemas.tenant_id",
            ],
            name="fk_database_tables_schema_connection_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_database_tables")),
        sa.UniqueConstraint(
            "connection_id",
            "schema_id",
            "table_name",
            name="uq_database_tables_connection_schema_name",
        ),
        sa.UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_database_tables_id_tenant",
        ),
    )
    op.create_index(
        "idx_database_tables_schema",
        "database_tables",
        ["schema_id"],
        unique=False,
    )
    op.create_index(
        "idx_database_tables_tenant_connection",
        "database_tables",
        ["tenant_id", "connection_id"],
        unique=False,
    )

    op.create_table(
        "database_columns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("column_name", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=100), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=True),
        sa.Column("is_nullable", sa.Boolean(), nullable=True),
        sa.Column(
            "is_primary_key",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_foreign_key",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_sensitive",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("referenced_schema", sa.String(length=255), nullable=True),
        sa.Column("referenced_table", sa.String(length=255), nullable=True),
        sa.Column("referenced_column", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sample_values",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(column_name) > 0",
            name=op.f("ck_database_columns_column_name_not_blank"),
        ),
        sa.CheckConstraint(
            "length(data_type) > 0",
            name=op.f("ck_database_columns_data_type_not_blank"),
        ),
        sa.CheckConstraint(
            "ordinal_position IS NULL OR ordinal_position > 0",
            name=op.f("ck_database_columns_ordinal_position_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["table_id", "tenant_id"],
            ["database_tables.id", "database_tables.tenant_id"],
            name="fk_database_columns_table_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_database_columns")),
        sa.UniqueConstraint(
            "table_id",
            "column_name",
            name="uq_database_columns_table_name",
        ),
    )
    op.create_index(
        "idx_database_columns_tenant_table",
        "database_columns",
        ["tenant_id", "table_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_database_columns_tenant_table",
        table_name="database_columns",
    )
    op.drop_table("database_columns")
    op.drop_index("idx_database_tables_tenant_connection", table_name="database_tables")
    op.drop_index("idx_database_tables_schema", table_name="database_tables")
    op.drop_table("database_tables")
    op.drop_index(
        "idx_database_schemas_tenant_connection",
        table_name="database_schemas",
    )
    op.drop_table("database_schemas")
    op.drop_index(
        "idx_database_connections_tenant_active",
        table_name="database_connections",
    )
    op.drop_index(
        "idx_database_connections_tenant",
        table_name="database_connections",
    )
    op.drop_table("database_connections")
