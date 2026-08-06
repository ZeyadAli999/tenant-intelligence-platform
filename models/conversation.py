"""Owner-scoped conversation and safe persisted message models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_conversations_id_tenant"),
        UniqueConstraint("id", "tenant_id", "user_id", name="uq_conversations_owner"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_conversations_user_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')", name="status_valid"
        ),
        Index(
            "idx_conversations_tenant_user_updated",
            "tenant_id",
            "user_id",
            "updated_at",
        ),
        Index("idx_conversations_tenant_last_message", "tenant_id", "last_message_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), default="active", server_default="active"
    )
    active_connection_ids: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    active_knowledge_base_ids: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    settings: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}"
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_messages_id_tenant"),
        UniqueConstraint(
            "id", "tenant_id", "conversation_id", name="uq_messages_conversation"
        ),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["conversations.id", "conversations.tenant_id"],
            name="fk_messages_conversation_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_message_id", "tenant_id", "conversation_id"],
            ["messages.id", "messages.tenant_id", "messages.conversation_id"],
            name="fk_messages_parent_conversation_tenant",
        ),
        CheckConstraint("role IN ('system', 'user', 'assistant')", name="role_valid"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'clarification', 'failed', 'cancelled')",
            name="status_valid",
        ),
        Index(
            "idx_messages_tenant_conversation_created",
            "tenant_id",
            "conversation_id",
            "created_at",
        ),
        Index("idx_messages_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_message_id: Mapped[UUID | None]
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(50), default="text", server_default="text"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}"
    )
    detected_intent: Mapped[str | None] = mapped_column(String(30))
    selected_sources: Mapped[list[object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, server_default="[]"
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    latency_ms: Mapped[int | None]
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
