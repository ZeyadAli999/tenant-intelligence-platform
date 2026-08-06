"""Add authentication and tenant identity tables.

Revision ID: 20260803_0002
Revises: 20260803_0001
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0002"
down_revision: str | None = "20260803_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="active", nullable=False
        ),
        sa.Column(
            "settings",
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
            "code = lower(trim(code))",
            name=op.f("ck_tenants_code_normalized"),
        ),
        sa.CheckConstraint(
            "length(code) > 0",
            name=op.f("ck_tenants_code_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name=op.f("ck_tenants_name_not_blank"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_tenants_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("code", name="uq_tenants_code"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="active", nullable=False
        ),
        sa.Column(
            "is_tenant_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            "email = lower(trim(email))",
            name=op.f("ck_users_email_normalized"),
        ),
        sa.CheckConstraint(
            "length(email) > 0",
            name=op.f("ck_users_email_not_blank"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_users_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_users_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_users_id_tenant"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"], unique=False)

    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "name = lower(trim(name))",
            name=op.f("ck_roles_name_normalized"),
        ),
        sa.CheckConstraint(
            "length(name) > 0",
            name=op.f("ck_roles_name_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_roles_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_roles_id_tenant"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_index("idx_roles_tenant_id", "roles", ["tenant_id"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["roles.id", "roles.tenant_id"],
            name="fk_user_roles_role_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_user_roles_user_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_index(
        "idx_user_roles_tenant_id",
        "user_roles",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_jti",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_jti"],
            ["refresh_tokens.jti"],
            name=op.f("fk_refresh_tokens_replaced_by_jti_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_refresh_tokens_user_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("jti", name="uq_refresh_tokens_jti"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index(
        "idx_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_tokens_family_id",
        "refresh_tokens",
        ["family_id"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_tokens_tenant_id",
        "refresh_tokens",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_tenant_id", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("idx_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("idx_user_roles_tenant_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("idx_roles_tenant_id", table_name="roles")
    op.drop_table("roles")
    op.drop_index("idx_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
