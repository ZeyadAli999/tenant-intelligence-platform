"""Database-only chat, SSE, and safe SQL metadata contracts."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from schemas.common import APIModel


class ChatRequest(APIModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000)
    database_connection_ids: list[UUID] = Field(default_factory=list, max_length=1)
    knowledge_base_ids: list[UUID] = Field(default_factory=list, max_length=10)
    stream: bool = False

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value.strip()

    @field_validator("database_connection_ids", "knowledge_base_ids")
    @classmethod
    def reject_duplicate_sources(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Source identifiers must be unique")
        return value


class SafeSQLInfo(APIModel):
    query_execution_id: UUID
    normalized_sql: str
    row_count: int
    truncated: bool


class DatabaseCitation(APIModel):
    type: Literal["database"] = "database"
    table: str
    query_execution_id: UUID | None = None
    columns: list[str] = Field(default_factory=list)


class DocumentCitation(APIModel):
    type: Literal["document"] = "document"
    file_id: UUID
    chunk_id: UUID
    file_name: str
    page_number: int | None = None
    section_title: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    relevance_score: float | None = None


Citation = Annotated[DatabaseCitation | DocumentCitation, Field(discriminator="type")]


class ChatUsage(APIModel):
    prompt_tokens: int
    completion_tokens: int
    provider_latency_ms: int


class ChatResponse(APIModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    intent: Literal["general", "database", "document", "hybrid", "clarification"]
    sources_used: list[str]
    sql: SafeSQLInfo | None = None
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    usage: ChatUsage


class MessageSQLResponse(APIModel):
    message_id: UUID
    query_execution_id: UUID
    normalized_sql: str
    execution_status: str | None
    row_count: int | None
    truncated: bool
    referenced_tables: list[str]
