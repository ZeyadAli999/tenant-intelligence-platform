"""Focused Phase 3C response, usage, history, SSE, and cancellation corrections."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from agents.graph import DatabaseChatGraph
from api.routes import chat as chat_routes
from app.config import Settings
from core.tenant_context import TenantContext
from models import Conversation, Message
from schemas.chat import ChatRequest
from services.chat_service import ChatService
from services.llm.fake_provider import FakeLLMProvider
from services.llm.schemas import (
    ProviderResult,
    ProviderUsage,
    RequestClassification,
    SourceSelectionContext,
)
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import bearer, login, seed_identity


class HistorySpyProvider(FakeLLMProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def classify(
        self,
        question: str,
        history: tuple[str, ...],
        source_selection: SourceSelectionContext,
    ):
        self.calls.append((question, history))
        return await super().classify(question, history, source_selection)


def test_usage_is_accumulated_across_generation_and_repair_stages() -> None:
    state = {}
    result = ProviderResult(
        RequestClassification(intent="database", confidence=1, short_reason="database"),
        "model",
        ProviderUsage(prompt_tokens=7, completion_tokens=3, latency_ms=11),
    )
    for stage in ("classification", "sql_proposal", "sql_repair", "answer_generation"):
        state.update(DatabaseChatGraph._usage(state, result, stage))
    assert state["prompt_tokens"] == 28
    assert state["completion_tokens"] == 12
    assert state["latency_ms"] == 44
    assert list(state["usage_by_stage"]) == [
        "classification",
        "sql_proposal",
        "sql_repair",
        "answer_generation",
    ]


def test_successful_database_response_uses_category_and_table_citations() -> None:
    service = object.__new__(ChatService)
    response = service.response(
        {
            "conversation_id": uuid4(),
            "assistant_message_id": uuid4(),
            "classification": RequestClassification(
                intent="database", confidence=1, short_reason="database"
            ),
            "answer": "Two rows.",
            "sources_used": ("database",),
            "referenced_tables": ("business.customers",),
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "latency_ms": 12,
        }
    )
    assert response.sources_used == ["database"]
    assert [item.table for item in response.citations] == ["business.customers"]
    assert response.usage.model_dump() == {
        "prompt_tokens": 20,
        "completion_tokens": 8,
        "provider_latency_ms": 12,
    }


@pytest.mark.asyncio
async def test_current_question_is_not_duplicated_in_classifier_history(
    api_client, test_database: DatabaseHarness
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])
    conversation = (
        await api_client.post(
            "/api/conversations", json={"title": "History"}, headers=headers
        )
    ).json()
    spy = HistorySpyProvider()
    app = api_client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[chat_routes.get_llm_provider] = lambda: spy
    await api_client.post(
        "/api/chat",
        json={"conversation_id": conversation["id"], "message": "hello"},
        headers=headers,
    )
    current = "What can you do now?"
    response = await api_client.post(
        "/api/chat",
        json={"conversation_id": conversation["id"], "message": current},
        headers=headers,
    )
    assert response.status_code == 200
    question, history = spy.calls[-1]
    assert question == current
    assert all(current not in item for item in history)
    assert [item.split(":", 1)[0] for item in history] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_sse_deltas_reconstruct_completed_answer(
    api_client, test_database: DatabaseHarness
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])
    conversation = (
        await api_client.post(
            "/api/conversations", json={"title": "SSE"}, headers=headers
        )
    ).json()
    response = await api_client.post(
        "/api/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "What can you do?",
            "stream": True,
        },
        headers=headers,
    )
    events: list[tuple[str, dict[str, object]]] = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        events.append(
            (
                lines[0].removeprefix("event: "),
                json.loads(lines[1].removeprefix("data: ")),
            )
        )
    deltas = [str(data["text"]) for name, data in events if name == "answer_delta"]
    completed = next(data for name, data in events if name == "completed")
    assert len(deltas) > 1
    assert "".join(deltas) == completed["answer"]
    assert [name for name, _ in events][:2] == ["started", "classified"]
    assert all("SELECT" not in delta and "SECRET" not in delta for delta in deltas)


@pytest.mark.asyncio
async def test_stream_close_persists_cancelled_status(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    conversation = Conversation(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        user_id=identity.user.id,
        title="cancel",
    )
    async with test_database.sessions() as session:
        session.add(conversation)
        await session.commit()
        service = ChatService(
            session,
            TenantContext(identity.user, identity.tenant, identity.roles),
            FakeLLMProvider(),
            Settings(),
        )
        stream = service.stream(
            ChatRequest(conversation_id=conversation.id, message="hello", stream=True)
        )
        await anext(stream)
        await stream.aclose()
    async with test_database.sessions() as session:
        assistant = await session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id, Message.role == "assistant"
            )
        )
        assert assistant is not None
        assert assistant.status == "cancelled"
        assert assistant.error_message == "Chat processing cancelled safely"


@pytest.mark.asyncio
async def test_database_source_category_is_persisted_on_assistant_message(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    conversation = Conversation(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        user_id=identity.user.id,
        title="sources",
    )
    assistant = Message(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        conversation_id=conversation.id,
        role="assistant",
        content="pending",
        status="pending",
    )
    async with test_database.sessions() as session:
        session.add(conversation)
        await session.flush()
        session.add(assistant)
        await session.commit()
        graph = DatabaseChatGraph(
            session,
            TenantContext(identity.user, identity.tenant, identity.roles),
            FakeLLMProvider(),
            Settings(),
        )
        await graph.persist_result(
            {
                "tenant_id": identity.tenant.id,
                "user_id": identity.user.id,
                "conversation_id": conversation.id,
                "assistant_message_id": assistant.id,
                "classification": RequestClassification(
                    intent="database", confidence=1, short_reason="database"
                ),
                "answer": "safe",
                "sources_used": ("database",),
                "status": "completed",
            }
        )
        await session.refresh(assistant)
        assert assistant.selected_sources == ["database"]
