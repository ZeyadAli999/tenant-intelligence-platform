"""Tenant-scoped knowledge-base, file, and citation API contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from schemas.common import APIModel

SafeName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class KnowledgeBaseCreateRequest(APIModel):
    name: SafeName
    description: str | None = Field(default=None, max_length=2000)


class KnowledgeBaseUpdateRequest(APIModel):
    name: SafeName | None = None
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "inactive"] | None = None


class KnowledgeBaseResponse(APIModel):
    id: UUID
    name: str
    description: str | None
    embedding_model: str
    embedding_dimension: int
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(APIModel):
    items: list[KnowledgeBaseResponse]
    total: int
    page: int
    page_size: int


class StoredFileResponse(APIModel):
    id: UUID
    knowledge_base_id: UUID
    original_name: str
    mime_type: str | None
    detected_mime_type: str
    extension: str
    file_size_bytes: int
    checksum: str
    processing_status: str
    processing_error_code: str | None
    processing_error_message: str | None
    processing_attempts: int
    page_count: int | None
    extracted_text_length: int | None
    chunk_count: int
    ingestion_version: int
    active_ingestion_version: int
    created_at: datetime
    processing_started_at: datetime | None
    processed_at: datetime | None
    updated_at: datetime


class StoredFileListResponse(APIModel):
    items: list[StoredFileResponse]
    total: int
    page: int
    page_size: int


class DatabaseMessageCitation(APIModel):
    type: Literal["database"] = "database"
    query_execution_id: UUID | None = None
    table: str
    columns: list[str] = Field(default_factory=list)


class DocumentMessageCitation(APIModel):
    type: Literal["document"] = "document"
    file_id: UUID
    chunk_id: UUID
    file_name: str
    page_number: int | None
    section_title: str | None
    sheet_name: str | None
    row_start: int | None
    row_end: int | None
    relevance_score: float | None


MessageCitationResponse = Annotated[
    DatabaseMessageCitation | DocumentMessageCitation, Field(discriminator="type")
]


class MessageCitationListResponse(APIModel):
    items: list[MessageCitationResponse]
