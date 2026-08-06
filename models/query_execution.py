"""Sanitized trace records for permission-controlled customer queries."""

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import UUIDPrimaryKeyMixin


class QueryExecution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "query_executions"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_query_executions_id_tenant"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["connection_id", "tenant_id"],
            ["database_connections.id", "database_connections.tenant_id"],
            name="fk_query_executions_connection_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["conversations.id", "conversations.tenant_id"],
            name="fk_query_executions_conversation_tenant",
        ),
        ForeignKeyConstraint(
            ["message_id", "tenant_id"],
            ["messages.id", "messages.tenant_id"],
            name="fk_query_executions_message_tenant",
        ),
        CheckConstraint("query_type IN ('select', 'with')", name="query_type_valid"),
        CheckConstraint(
            "validation_status IN ('accepted', 'rejected')",
            name="validation_status_valid",
        ),
        CheckConstraint(
            "execution_status IS NULL OR execution_status IN "
            "('pending', 'succeeded', 'failed', 'timeout', 'rejected')",
            name="execution_status_valid",
        ),
        Index("idx_query_executions_tenant_created", "tenant_id", "created_at"),
        Index("idx_query_executions_connection", "connection_id"),
        Index("idx_query_executions_message", "tenant_id", "message_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[UUID | None]
    message_id: Mapped[UUID | None]
    connection_id: Mapped[UUID] = mapped_column(nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_sql: Mapped[str | None] = mapped_column(Text)
    query_type: Mapped[str | None] = mapped_column(String(30))
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    validation_errors: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    applied_row_filters: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}"
    )
    referenced_tables: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    referenced_columns: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    execution_status: Mapped[str | None] = mapped_column(String(30))
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    returned_row_count: Mapped[int | None] = mapped_column(Integer)
    result_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    result_preview: Mapped[list[object] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
