"""Typed state containing approved database-chat orchestration data only."""

from typing import TypedDict
from uuid import UUID

from services.documents.retrieval import RetrievedEvidence
from services.llm.schemas import (
    RequestClassification,
    SourceSelectionContext,
    SQLProposal,
)


class ChatState(TypedDict, total=False):
    tenant_id: UUID
    user_id: UUID
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    question: str
    connection_id: UUID | None
    knowledge_base_ids: tuple[UUID, ...]
    safe_history: tuple[str, ...]
    classification: RequestClassification
    source_selection: SourceSelectionContext
    model_classified_intent: str
    resolved_executable_intent: str
    compact_schema: str
    visible_tables: tuple[str, ...]
    sql_proposal: SQLProposal
    repair_count: int
    safe_error_codes: tuple[str, ...]
    query_execution_id: UUID
    safe_normalized_sql: str
    approved_columns: tuple[str, ...]
    masked_rows: tuple[dict[str, object], ...]
    row_count: int
    truncated: bool
    referenced_tables: tuple[str, ...]
    answer: str
    warnings: tuple[str, ...]
    sources_used: tuple[str, ...]
    model_name: str
    provider_name: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    usage_by_stage: dict[str, dict[str, int | str]]
    status: str
    document_query: str
    document_evidence: tuple[RetrievedEvidence, ...]
    document_citations: tuple[dict[str, object], ...]
