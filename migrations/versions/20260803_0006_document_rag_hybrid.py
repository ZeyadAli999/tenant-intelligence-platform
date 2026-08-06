"""Add tenant-isolated document RAG, pgvector, and message citations.

Revision ID: 20260803_0006
Revises: 20260803_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "20260803_0006"
down_revision: str | None = "20260803_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_unique_constraint(
        "uq_query_executions_id_tenant", "query_executions", ["id", "tenant_id"]
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "chunking_config", postgresql.JSONB(), server_default="{}", nullable=False
        ),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_knowledge_bases_creator_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_knowledge_bases_id_tenant"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_knowledge_bases_tenant_name"),
        sa.CheckConstraint(
            "status IN ('active','inactive','deleted')", name="kb_status_valid"
        ),
        sa.CheckConstraint(
            "embedding_dimension = 384", name="kb_embedding_dimension_384"
        ),
    )
    op.create_index("idx_knowledge_bases_tenant", "knowledge_bases", ["tenant_id"])
    op.create_index(
        "idx_knowledge_bases_creator", "knowledge_bases", ["tenant_id", "created_by"]
    )

    op.create_table(
        "files",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False, unique=True),
        sa.Column("storage_bucket", sa.String(100), nullable=False),
        sa.Column("mime_type", sa.String(150)),
        sa.Column("detected_mime_type", sa.String(150), nullable=False),
        sa.Column("extension", sa.String(20), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "processing_status", sa.String(30), server_default="pending", nullable=False
        ),
        sa.Column("processing_error_code", sa.String(80)),
        sa.Column("processing_error_message", sa.String(300)),
        sa.Column(
            "processing_attempts", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("page_count", sa.Integer()),
        sa.Column("extracted_text_length", sa.Integer()),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "ingestion_version", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "active_ingestion_version", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), primary_key=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id", "tenant_id"],
            ["knowledge_bases.id", "knowledge_bases.tenant_id"],
            name="fk_files_kb_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_files_uploader_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_files_id_tenant"),
        sa.UniqueConstraint(
            "id", "tenant_id", "knowledge_base_id", name="uq_files_kb_tenant"
        ),
        sa.CheckConstraint(
            "processing_status IN ('pending','processing','ready','failed','deleting','deleted')",
            name="file_processing_status_valid",
        ),
        sa.CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        sa.CheckConstraint(
            "ingestion_version >= 1", name="file_ingestion_version_positive"
        ),
        sa.CheckConstraint(
            "active_ingestion_version >= 0 AND "
            "active_ingestion_version <= ingestion_version",
            name="file_active_ingestion_version_valid",
        ),
    )
    op.create_index("idx_files_tenant", "files", ["tenant_id"])
    op.create_index("idx_files_kb", "files", ["tenant_id", "knowledge_base_id"])
    op.create_index("idx_files_status", "files", ["tenant_id", "processing_status"])
    op.create_index("idx_files_checksum", "files", ["tenant_id", "checksum"])
    op.create_index(
        "uq_files_active_checksum",
        "files",
        ["tenant_id", "knowledge_base_id", "checksum"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_version", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section_title", sa.String(500)),
        sa.Column("sheet_name", sa.String(255)),
        sa.Column("row_start", sa.Integer()),
        sa.Column("row_end", sa.Integer()),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple'::regconfig, content)", persisted=True),
        ),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id", "tenant_id"],
            ["knowledge_bases.id", "knowledge_bases.tenant_id"],
            name="fk_chunks_kb_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "tenant_id", "knowledge_base_id"],
            ["files.id", "files.tenant_id", "files.knowledge_base_id"],
            name="fk_chunks_file_kb_tenant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_document_chunks_id_tenant"),
        sa.UniqueConstraint(
            "file_id",
            "ingestion_version",
            "chunk_index",
            name="uq_file_generation_chunk",
        ),
        sa.CheckConstraint("length(trim(content)) > 0", name="chunk_content_nonempty"),
        sa.CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        sa.CheckConstraint("token_count > 0", name="chunk_token_count_positive"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="chunk_page_positive"
        ),
        sa.CheckConstraint(
            "(row_start IS NULL AND row_end IS NULL) OR (row_start > 0 AND row_end >= row_start)",
            name="chunk_row_range_valid",
        ),
    )
    op.create_index("idx_document_chunks_tenant", "document_chunks", ["tenant_id"])
    op.create_index(
        "idx_document_chunks_kb", "document_chunks", ["tenant_id", "knowledge_base_id"]
    )
    op.create_index(
        "idx_document_chunks_file",
        "document_chunks",
        ["tenant_id", "file_id", "ingestion_version"],
    )
    op.execute(
        "CREATE INDEX idx_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX idx_document_chunks_search_gin ON document_chunks USING gin (search_vector)"
    )

    op.create_table(
        "message_citations",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("citation_type", sa.String(30), nullable=False),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("chunk_id", sa.Uuid()),
        sa.Column("query_execution_id", sa.Uuid()),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("page_number", sa.Integer()),
        sa.Column("relevance_score", sa.Float()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["message_id", "tenant_id"],
            ["messages.id", "messages.tenant_id"],
            name="fk_citations_message_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_citations_file_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "tenant_id"],
            ["document_chunks.id", "document_chunks.tenant_id"],
            name="fk_citations_chunk_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["query_execution_id", "tenant_id"],
            ["query_executions.id", "query_executions.tenant_id"],
            name="fk_citations_query_tenant",
        ),
        sa.CheckConstraint(
            "citation_type IN ('database','document')", name="citation_type_valid"
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="citation_page_positive"
        ),
    )
    op.create_index("idx_message_citations_tenant", "message_citations", ["tenant_id"])
    op.create_index(
        "idx_message_citations_message",
        "message_citations",
        ["tenant_id", "message_id"],
    )
    op.create_index(
        "idx_message_citations_type",
        "message_citations",
        ["tenant_id", "citation_type"],
    )


def downgrade() -> None:
    op.drop_table("message_citations")
    op.drop_table("document_chunks")
    op.drop_table("files")
    op.drop_table("knowledge_bases")
    op.drop_constraint(
        "uq_query_executions_id_tenant", "query_executions", type_="unique"
    )
