"""Tenant-owned runtime customer database connections."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


def normalize_connection_name(value: str) -> str:
    return value.strip().casefold()


def normalize_database_type(value: str) -> str:
    return value.strip().casefold()


class DatabaseConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_database_connections_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_database_connections_creator_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_database_connections_tenant_name",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_database_connections_id_tenant",
        ),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        CheckConstraint("name = lower(trim(name))", name="name_normalized"),
        CheckConstraint("length(database_type) > 0", name="database_type_not_blank"),
        CheckConstraint(
            "database_type = lower(trim(database_type))",
            name="database_type_normalized",
        ),
        CheckConstraint("length(trim(host)) > 0", name="host_not_blank"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="port_valid"),
        CheckConstraint(
            "length(trim(database_name)) > 0", name="database_name_not_blank"
        ),
        CheckConstraint("length(trim(username)) > 0", name="username_not_blank"),
        CheckConstraint(
            "length(encrypted_password) > 0", name="encrypted_password_not_blank"
        ),
        CheckConstraint(
            "status IN ('pending', 'connected', 'failed')",
            name="status_valid",
        ),
        CheckConstraint(
            "schema_sync_status IN ('pending', 'running', 'succeeded', 'failed')",
            name="schema_sync_status_valid",
        ),
        Index("idx_database_connections_tenant", "tenant_id"),
        Index("idx_database_connections_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    database_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    ssl_settings: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    connection_options: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_message: Mapped[str | None] = mapped_column(Text)
    schema_sync_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    last_schema_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    @validates("name")
    def validate_name(self, _: str, value: str) -> str:
        return normalize_connection_name(value)

    @validates("database_type")
    def validate_database_type(self, _: str, value: str) -> str:
        return normalize_database_type(value)
