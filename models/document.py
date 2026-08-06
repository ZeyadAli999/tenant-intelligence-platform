"""Tenant-isolated document ingestion, vector metadata, and citation models."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_knowledge_bases_id_tenant"),
        UniqueConstraint("tenant_id", "name", name="uq_knowledge_bases_tenant_name"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["created_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_knowledge_bases_creator_tenant",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'deleted')", name="kb_status_valid"
        ),
        CheckConstraint("embedding_dimension = 384", name="kb_embedding_dimension_384"),
        Index("idx_knowledge_bases_tenant", "tenant_id"),
        Index("idx_knowledge_bases_creator", "tenant_id", "created_by"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(
        Integer, nullable=False, default=384
    )
    chunking_config: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(30), default="active", server_default="active"
    )


class StoredFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_files_id_tenant"),
        UniqueConstraint(
            "id", "tenant_id", "knowledge_base_id", name="uq_files_kb_tenant"
        ),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["knowledge_base_id", "tenant_id"],
            ["knowledge_bases.id", "knowledge_bases.tenant_id"],
            name="fk_files_kb_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["uploaded_by", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_files_uploader_tenant",
        ),
        CheckConstraint(
            "processing_status IN ('pending','processing','ready','failed','deleting','deleted')",
            name="file_processing_status_valid",
        ),
        CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        CheckConstraint(
            "ingestion_version >= 1", name="file_ingestion_version_positive"
        ),
        CheckConstraint(
            "active_ingestion_version >= 0 AND "
            "active_ingestion_version <= ingestion_version",
            name="file_active_ingestion_version_valid",
        ),
        Index("idx_files_tenant", "tenant_id"),
        Index("idx_files_kb", "tenant_id", "knowledge_base_id"),
        Index("idx_files_status", "tenant_id", "processing_status"),
        Index("idx_files_checksum", "tenant_id", "checksum"),
        Index(
            "uq_files_active_checksum",
            "tenant_id",
            "knowledge_base_id",
            "checksum",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    knowledge_base_id: Mapped[UUID] = mapped_column(nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    detected_mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending"
    )
    processing_error_code: Mapped[str | None] = mapped_column(String(80))
    processing_error_message: Mapped[str | None] = mapped_column(String(300))
    processing_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    page_count: Mapped[int | None]
    extracted_text_length: Mapped[int | None]
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ingestion_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    active_ingestion_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    file_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default="{}",
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_document_chunks_id_tenant"),
        UniqueConstraint(
            "file_id",
            "ingestion_version",
            "chunk_index",
            name="uq_file_generation_chunk",
        ),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["knowledge_base_id", "tenant_id"],
            ["knowledge_bases.id", "knowledge_bases.tenant_id"],
            name="fk_chunks_kb_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id", "tenant_id", "knowledge_base_id"],
            ["files.id", "files.tenant_id", "files.knowledge_base_id"],
            name="fk_chunks_file_kb_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("length(trim(content)) > 0", name="chunk_content_nonempty"),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("token_count > 0", name="chunk_token_count_positive"),
        CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="chunk_page_positive"
        ),
        CheckConstraint(
            "(row_start IS NULL AND row_end IS NULL) OR (row_start > 0 AND row_end >= row_start)",
            name="chunk_row_range_valid",
        ),
        Index("idx_document_chunks_tenant", "tenant_id"),
        Index("idx_document_chunks_kb", "tenant_id", "knowledge_base_id"),
        Index("idx_document_chunks_file", "tenant_id", "file_id", "ingestion_version"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    knowledge_base_id: Mapped[UUID] = mapped_column(nullable=False)
    file_id: Mapped[UUID] = mapped_column(nullable=False)
    ingestion_version: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int | None]
    section_title: Mapped[str | None] = mapped_column(String(500))
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    row_start: Mapped[int | None]
    row_end: Mapped[int | None]
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default="{}",
    )
    embedding: Mapped[list[float]] = mapped_column(VECTOR(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MessageCitation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["message_id", "tenant_id"],
            ["messages.id", "messages.tenant_id"],
            name="fk_citations_message_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_citations_file_tenant",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "tenant_id"],
            ["document_chunks.id", "document_chunks.tenant_id"],
            name="fk_citations_chunk_tenant",
        ),
        ForeignKeyConstraint(
            ["query_execution_id", "tenant_id"],
            ["query_executions.id", "query_executions.tenant_id"],
            name="fk_citations_query_tenant",
        ),
        CheckConstraint(
            "citation_type IN ('database','document')", name="citation_type_valid"
        ),
        CheckConstraint(
            "page_number IS NULL OR page_number > 0", name="citation_page_positive"
        ),
        Index("idx_message_citations_tenant", "tenant_id"),
        Index("idx_message_citations_message", "tenant_id", "message_id"),
        Index("idx_message_citations_type", "tenant_id", "citation_type"),
    )

    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    message_id: Mapped[UUID] = mapped_column(nullable=False)
    citation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_id: Mapped[UUID | None]
    chunk_id: Mapped[UUID | None]
    query_execution_id: Mapped[UUID | None]
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    page_number: Mapped[int | None]
    relevance_score: Mapped[float | None] = mapped_column(Float)
    citation_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
