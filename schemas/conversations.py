"""Owner-scoped conversation and message API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from schemas.common import APIModel


class ConversationCreateRequest(APIModel):
    title: str | None = Field(default=None, max_length=255)
    database_connection_ids: list[UUID] = Field(default_factory=list, max_length=1)
    knowledge_base_ids: list[UUID] = Field(default_factory=list, max_length=10)

    @field_validator("database_connection_ids")
    @classmethod
    def unique_connections(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Connection IDs must be unique")
        return value

    @field_validator("knowledge_base_ids")
    @classmethod
    def unique_knowledge_bases(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Knowledge base IDs must be unique")
        return value


class MessageResponse(APIModel):
    id: UUID
    parent_message_id: UUID | None
    role: str
    message_type: str
    content: str
    detected_intent: str | None
    selected_sources: list[object]
    status: str
    model_name: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


class ConversationResponse(APIModel):
    id: UUID
    title: str | None
    status: str
    database_connection_ids: list[UUID]
    knowledge_base_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None


class ConversationListResponse(APIModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]
    message_total: int
    message_page: int
    message_page_size: int
