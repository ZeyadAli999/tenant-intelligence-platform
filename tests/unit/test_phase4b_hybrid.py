"""Phase 4B evidence, citation, source-category, and SSE contracts."""

from uuid import uuid4

import pytest

from agents.graph import DatabaseChatGraph
from app.config import Settings
from core.tenant_context import TenantContext
from schemas.chat import DocumentCitation
from services.chat_service import ChatService
from services.llm.fake_provider import FakeLLMProvider
from services.llm.schemas import (
    HybridGroundedAnswer,
    ProviderResult,
    RequestClassification,
    SQLProposal,
)
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity


class InvalidHybridCitationProvider(FakeLLMProvider):
    async def generate_hybrid_answer(self, question, evidence):
        return ProviderResult(
            HybridGroundedAnswer(
                answer="unsafe",
                used_evidence_ids=["DOC999"],
                insufficient_evidence=False,
            ),
            self.model,
        )


def hybrid_state() -> dict[str, object]:
    return {
        "conversation_id": uuid4(),
        "assistant_message_id": uuid4(),
        "classification": RequestClassification(
            intent="hybrid", confidence=1, short_reason="hybrid"
        ),
        "answer": "The approved database result agrees with the cited contract evidence.",
        "sources_used": ("database", "documents"),
        "query_execution_id": uuid4(),
        "safe_normalized_sql": "SELECT count(id) AS customer_count FROM business.customers",
        "row_count": 1,
        "truncated": False,
        "referenced_tables": ("business.customers",),
        "document_citations": (
            {
                "type": "document",
                "file_id": uuid4(),
                "chunk_id": uuid4(),
                "file_name": "contract.pdf",
                "page_number": 2,
                "section_title": "Commercial terms",
                "relevance_score": 0.9,
            },
        ),
        "prompt_tokens": 45,
        "completion_tokens": 12,
        "latency_ms": 70,
    }


def test_hybrid_response_uses_source_categories_and_both_citation_types() -> None:
    service = object.__new__(ChatService)
    response = service.response(hybrid_state())  # type: ignore[arg-type]
    assert response.sources_used == ["database", "documents"]
    assert [item.type for item in response.citations] == ["database", "document"]
    document = response.citations[1]
    assert isinstance(document, DocumentCitation)
    assert document.file_name == "contract.pdf" and document.page_number == 2
    assert response.usage.prompt_tokens == 45
    assert response.usage.completion_tokens == 12
    assert response.usage.provider_latency_ms == 70


def test_hybrid_sse_deltas_reconstruct_answer_after_validated_sql() -> None:
    state = hybrid_state()
    events = ChatService._public_events("hybrid_chat", state)  # type: ignore[arg-type]
    names = [name for name, _ in events]
    assert names[:2] == ["query_validated", "query_executed"]
    assert all(name == "answer_delta" for name in names[2:])
    reconstructed = "".join(str(data["text"]) for _, data in events[2:])
    assert reconstructed == state["answer"]
    assert "SENTINEL_DOCUMENT_SECRET" not in reconstructed


def test_hybrid_answer_is_split_into_multiple_ordered_deltas() -> None:
    events = ChatService._public_events("hybrid_chat", hybrid_state())
    deltas = [data for name, data in events if name == "answer_delta"]
    assert len(deltas) > 1


@pytest.mark.asyncio
async def test_unknown_hybrid_evidence_id_fails_closed(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    async with test_database.sessions() as session:
        graph = DatabaseChatGraph(
            session,
            TenantContext(identity.user, identity.tenant, identity.roles),
            InvalidHybridCitationProvider(),
            Settings(),
        )

        async def schema(_):
            return {"compact_schema": "approved", "visible_tables": ("safe.table",)}

        async def sql(_):
            return {
                "sql_proposal": SQLProposal(
                    action="generate_sql",
                    sql="SELECT 1 AS value",
                    short_description="safe",
                )
            }

        async def execute(_):
            return {
                "query_execution_id": uuid4(),
                "masked_rows": ({"value": 1},),
                "approved_columns": ("value",),
                "row_count": 1,
                "truncated": False,
                "referenced_tables": ("safe.table",),
            }

        async def rewrite(_):
            return {"document_query": "safe"}

        async def retrieve(_):
            return {"document_evidence": ()}

        graph.retrieve_schema = schema  # type: ignore[method-assign]
        graph.generate_sql = sql  # type: ignore[method-assign]
        graph.validate_execute = execute  # type: ignore[method-assign]
        graph.rewrite_document_query = rewrite  # type: ignore[method-assign]
        graph.retrieve_documents = retrieve  # type: ignore[method-assign]
        result = await graph.hybrid_chat(
            {
                "tenant_id": identity.tenant.id,
                "user_id": identity.user.id,
                "question": "hybrid database and document question",
                "connection_id": uuid4(),
                "knowledge_base_ids": (uuid4(),),
            }
        )
        assert result["status"] == "failed"
        assert result["sources_used"] == ()
        assert "grounded safely" in result["answer"]
