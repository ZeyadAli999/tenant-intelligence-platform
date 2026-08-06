"""Tenant-consistent table and column authorization records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import UUIDPrimaryKeyMixin

MASK_TYPES = ("redact", "partial", "hash", "null")


class TablePermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "table_permissions"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["roles.id", "roles.tenant_id"],
            name="fk_table_permissions_role_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_table_permissions_user_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_table_permissions_connection_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["table_id", "connection_id", "tenant_id"],
            [
                "database_tables.id",
                "database_tables.connection_id",
                "database_tables.tenant_id",
            ],
            name="fk_table_permissions_table_connection_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(role_id IS NOT NULL AND user_id IS NULL) OR "
            "(role_id IS NULL AND user_id IS NOT NULL)",
            name="subject_exactly_one",
        ),
        CheckConstraint(
            "NOT can_insert AND NOT can_update AND NOT can_delete",
            name="chat_read_only",
        ),
        UniqueConstraint(
            "id", "table_id", "tenant_id", name="uq_table_permissions_id_table_tenant"
        ),
        Index(
            "uq_table_permissions_user_table",
            "user_id",
            "table_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
            sqlite_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_table_permissions_role_table",
            "role_id",
            "table_id",
            unique=True,
            postgresql_where=text("role_id IS NOT NULL"),
            sqlite_where=text("role_id IS NOT NULL"),
        ),
        Index("idx_table_permissions_tenant_connection", "tenant_id", "connection_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    role_id: Mapped[UUID | None]
    user_id: Mapped[UUID | None]
    connection_id: Mapped[UUID] = mapped_column(nullable=False)
    table_id: Mapped[UUID] = mapped_column(nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    can_insert: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    can_update: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    can_delete: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    row_filter: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ColumnPermission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "column_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["table_permission_id", "table_id", "tenant_id"],
            [
                "table_permissions.id",
                "table_permissions.table_id",
                "table_permissions.tenant_id",
            ],
            name="fk_column_permissions_table_permission_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["column_id", "table_id", "tenant_id"],
            [
                "database_columns.id",
                "database_columns.table_id",
                "database_columns.tenant_id",
            ],
            name="fk_column_permissions_column_table_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "table_permission_id",
            "column_id",
            name="uq_column_permissions_permission_column",
        ),
        CheckConstraint(
            "mask_type IS NULL OR mask_type IN ('redact', 'partial', 'hash', 'null')",
            name="mask_type_valid",
        ),
        Index("idx_column_permissions_tenant_table", "tenant_id", "table_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    table_id: Mapped[UUID] = mapped_column(nullable=False)
    table_permission_id: Mapped[UUID] = mapped_column(nullable=False)
    column_id: Mapped[UUID] = mapped_column(nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    can_filter: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    can_aggregate: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    mask_type: Mapped[str | None] = mapped_column(String(50))
