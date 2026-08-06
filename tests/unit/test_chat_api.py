"""Phase 3C owner isolation, deterministic routing, persistence, and SSE tests."""

import pytest
from sqlalchemy import select

from models import KnowledgeBase, Message
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import bearer, login, seed_identity


async def create_conversation(client, database: DatabaseHarness):
    identity = await seed_identity(database)
    tokens = await login(client, identity)
    headers = bearer(tokens["access_token"])
    response = await client.post(
        "/api/conversations", json={"title": "Database questions"}, headers=headers
    )
    assert response.status_code == 201
    return identity, headers, response.json()["id"]


@pytest.mark.asyncio
async def test_general_chat_is_persisted_without_database_access(
    api_client, test_database: DatabaseHarness
) -> None:
    identity, headers, conversation_id = await create_conversation(
        api_client, test_database
    )
    response = await api_client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "What can you do?"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "general"
    assert body["sql"] is None
    assert body["sources_used"] == []
    assert response.headers["X-Request-ID"]
    async with test_database.sessions() as session:
        messages = list(
            (
                await session.scalars(
                    select(Message).where(Message.tenant_id == identity.tenant.id)
                )
            ).all()
        )
    assert [item.role for item in messages] == ["user", "assistant"]
    assert all(item.status == "completed" for item in messages)
    assert messages[1].prompt_version == "phase3c_v1"


@pytest.mark.asyncio
async def test_document_request_without_knowledge_base_asks_for_clarification(
    api_client, test_database: DatabaseHarness
) -> None:
    _, headers, conversation_id = await create_conversation(api_client, test_database)
    response = await api_client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Search my uploaded document",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "clarification"
    assert "source" in response.json()["answer"].casefold()


@pytest.mark.asyncio
async def test_database_chat_without_source_asks_for_clarification(
    api_client, test_database: DatabaseHarness
) -> None:
    _, headers, conversation_id = await create_conversation(api_client, test_database)
    response = await api_client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "How many customers are there?",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "clarification"
    assert "source" in response.json()["answer"].casefold()


@pytest.mark.asyncio
async def test_chat_is_owner_scoped_and_tenant_input_is_not_accepted(
    api_client, test_database: DatabaseHarness
) -> None:
    _, _, conversation_id = await create_conversation(api_client, test_database)
    other = await seed_identity(
        test_database, tenant_code="other", email="admin@other.example"
    )
    tokens = await login(api_client, other)
    response = await api_client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "hello",
            "tenant_id": str(other.tenant.id),
        },
        headers=bearer(tokens["access_token"]),
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}


@pytest.mark.asyncio
async def test_cross_tenant_selected_knowledge_base_is_404_before_classification(
    api_client, test_database: DatabaseHarness
) -> None:
    _, headers, conversation_id = await create_conversation(api_client, test_database)
    other = await seed_identity(
        test_database, tenant_code="chat-other", email="chat@other.example"
    )
    kb_id = other.user.id
    async with test_database.sessions() as session:
        session.add(
            KnowledgeBase(
                id=kb_id,
                tenant_id=other.tenant.id,
                created_by=other.user.id,
                name="Other tenant evidence",
                embedding_model="deterministic",
                embedding_dimension=384,
            )
        )
        await session.commit()
    response = await api_client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "message": "Read the other tenant evidence",
            "knowledge_base_ids": [str(kb_id)],
        },
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Resource not found"}


@pytest.mark.asyncio
async def test_stream_emits_named_events_and_completed_contract(
    api_client, test_database: DatabaseHarness
) -> None:
    _, headers, conversation_id = await create_conversation(api_client, test_database)
    response = await api_client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "message": "hello", "stream": True},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: started" in response.text
    assert "event: classified" in response.text
    assert "event: answer_delta" in response.text
    assert "event: completed" in response.text


@pytest.mark.asyncio
async def test_message_sql_is_owner_scoped_and_requires_execution(
    api_client, test_database: DatabaseHarness
) -> None:
    _, headers, conversation_id = await create_conversation(api_client, test_database)
    chat = await api_client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "hello"},
        headers=headers,
    )
    response = await api_client.get(
        f"/api/messages/{chat.json()['message_id']}/sql", headers=headers
    )
    assert response.status_code == 404
