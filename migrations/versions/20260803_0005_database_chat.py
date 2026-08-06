"""Add owner-scoped conversations, messages, and query trace linkage.

Revision ID: 20260803_0005
Revises: 20260803_0004
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0005"
down_revision: str | None = "20260803_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column(
            "active_connection_ids",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "active_knowledge_base_ids",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("settings", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')",
            name="ck_conversations_status_valid",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_conversations_user_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_conversations_id_tenant"),
        sa.UniqueConstraint(
            "id", "tenant_id", "user_id", name="uq_conversations_owner"
        ),
    )
    op.create_index(
        "idx_conversations_tenant_user_updated",
        "conversations",
        ["tenant_id", "user_id", "updated_at"],
    )
    op.create_index(
        "idx_conversations_tenant_last_message",
        "conversations",
        ["tenant_id", "last_message_at"],
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("message_type", sa.String(50), server_default="text", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "structured_content",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("detected_intent", sa.String(30)),
        sa.Column(
            "selected_sources", postgresql.JSONB(), server_default="[]", nullable=False
        ),
        sa.Column("model_name", sa.String(100)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('system', 'user', 'assistant')", name="ck_messages_role_valid"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'clarification', 'failed', 'cancelled')",
            name="ck_messages_status_valid",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "tenant_id"],
            ["conversations.id", "conversations.tenant_id"],
            name="fk_messages_conversation_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_message_id", "tenant_id", "conversation_id"],
            ["messages.id", "messages.tenant_id", "messages.conversation_id"],
            name="fk_messages_parent_conversation_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_messages_id_tenant"),
        sa.UniqueConstraint(
            "id", "tenant_id", "conversation_id", name="uq_messages_conversation"
        ),
    )
    op.create_index(
        "idx_messages_tenant_conversation_created",
        "messages",
        ["tenant_id", "conversation_id", "created_at"],
    )
    op.create_index(
        "idx_messages_tenant_created", "messages", ["tenant_id", "created_at"]
    )
    op.create_foreign_key(
        "fk_query_executions_conversation_tenant",
        "query_executions",
        "conversations",
        ["conversation_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_foreign_key(
        "fk_query_executions_message_tenant",
        "query_executions",
        "messages",
        ["message_id", "tenant_id"],
        ["id", "tenant_id"],
    )
    op.create_index(
        "idx_query_executions_message", "query_executions", ["tenant_id", "message_id"]
    )
    op.add_column(
        "query_executions",
        sa.Column(
            "result_truncated", sa.Boolean(), server_default="false", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("query_executions", "result_truncated")
    op.drop_index("idx_query_executions_message", table_name="query_executions")
    op.drop_constraint(
        "fk_query_executions_message_tenant", "query_executions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_query_executions_conversation_tenant",
        "query_executions",
        type_="foreignkey",
    )
    op.drop_index("idx_messages_tenant_created", table_name="messages")
    op.drop_index("idx_messages_tenant_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("idx_conversations_tenant_last_message", table_name="conversations")
    op.drop_index("idx_conversations_tenant_user_updated", table_name="conversations")
    op.drop_table("conversations")
