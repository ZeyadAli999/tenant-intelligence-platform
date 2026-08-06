"""Tenant-consistent cached customer database metadata."""

from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DatabaseSchema(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_schemas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_database_schemas_connection_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "connection_id",
            "schema_name",
            name="uq_database_schemas_connection_name",
        ),
        UniqueConstraint(
            "id",
            "connection_id",
            "tenant_id",
            name="uq_database_schemas_id_connection_tenant",
        ),
        CheckConstraint("length(schema_name) > 0", name="schema_name_not_blank"),
        Index("idx_database_schemas_tenant_connection", "tenant_id", "connection_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    connection_id: Mapped[UUID] = mapped_column(nullable=False)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class DatabaseTable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_tables"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_database_tables_connection_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["schema_id", "connection_id", "tenant_id"],
            [
                "database_schemas.id",
                "database_schemas.connection_id",
                "database_schemas.tenant_id",
            ],
            name="fk_database_tables_schema_connection_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "connection_id",
            "schema_id",
            "table_name",
            name="uq_database_tables_connection_schema_name",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_database_tables_id_tenant",
        ),
        UniqueConstraint(
            "id",
            "connection_id",
            "tenant_id",
            name="uq_database_tables_id_connection_tenant",
        ),
        CheckConstraint("length(table_name) > 0", name="table_name_not_blank"),
        CheckConstraint("table_type IN ('table', 'view')", name="table_type_valid"),
        CheckConstraint(
            "estimated_row_count IS NULL OR estimated_row_count >= 0",
            name="estimated_row_count_valid",
        ),
        Index("idx_database_tables_tenant_connection", "tenant_id", "connection_id"),
        Index("idx_database_tables_schema", "schema_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    connection_id: Mapped[UUID] = mapped_column(nullable=False)
    schema_id: Mapped[UUID] = mapped_column(nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="table",
        server_default="table",
    )
    description: Mapped[str | None] = mapped_column(Text)
    estimated_row_count: Mapped[int | None] = mapped_column(BigInteger)
    primary_key_columns: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default="[]",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )


class DatabaseColumn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "database_columns"
    __table_args__ = (
        ForeignKeyConstraint(
            ["table_id", "tenant_id"],
            ["database_tables.id", "database_tables.tenant_id"],
            name="fk_database_columns_table_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "table_id",
            "column_name",
            name="uq_database_columns_table_name",
        ),
        UniqueConstraint(
            "id",
            "table_id",
            "tenant_id",
            name="uq_database_columns_id_table_tenant",
        ),
        CheckConstraint("length(column_name) > 0", name="column_name_not_blank"),
        CheckConstraint("length(data_type) > 0", name="data_type_not_blank"),
        CheckConstraint(
            "ordinal_position IS NULL OR ordinal_position > 0",
            name="ordinal_position_valid",
        ),
        Index("idx_database_columns_tenant_table", "tenant_id", "table_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    table_id: Mapped[UUID] = mapped_column(nullable=False)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    ordinal_position: Mapped[int | None] = mapped_column(Integer)
    is_nullable: Mapped[bool | None]
    is_primary_key: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_foreign_key: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    referenced_schema: Mapped[str | None] = mapped_column(String(255))
    referenced_table: Mapped[str | None] = mapped_column(String(255))
    referenced_column: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    sample_values: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default="[]",
    )
