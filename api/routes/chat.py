"""Database-only chat endpoints, including server-sent events."""

import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.exceptions import ResourceNotFoundError
from core.tenant_context import TenantContext, get_tenant_context
from repositories.conversations import ConversationRepository
from repositories.documents import DocumentRepository
from schemas.chat import ChatRequest, ChatResponse, MessageSQLResponse
from schemas.documents import (
    DatabaseMessageCitation,
    DocumentMessageCitation,
    MessageCitationListResponse,
)
from services.chat_service import ChatService
from services.documents.embeddings import EmbeddingService, FastEmbedService
from services.llm.base import LLMProvider

router = APIRouter(tags=["chat"])


def get_llm_provider(request: Request) -> LLMProvider:
    return request.app.state.llm_provider


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return FastEmbedService(get_settings())


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embeddings: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> ChatResponse:
    return await ChatService(
        session, context, provider, get_settings(), embeddings
    ).run(payload)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embeddings: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> StreamingResponse:
    service = ChatService(session, context, provider, get_settings(), embeddings)

    async def events() -> AsyncIterator[str]:
        async for name, data in service.stream(payload):
            yield f"event: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/messages/{message_id}/sql", response_model=MessageSQLResponse)
async def message_sql(
    message_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> MessageSQLResponse:
    return await ChatService(session, context, provider, settings).message_sql(
        message_id
    )


@router.get(
    "/messages/{message_id}/citations", response_model=MessageCitationListResponse
)
async def message_citations(
    message_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageCitationListResponse:
    message = await ConversationRepository(session).message(
        context.tenant.id, context.user.id, message_id
    )
    if message is None:
        raise ResourceNotFoundError
    repository = DocumentRepository(session)
    rows = await repository.citations(context.tenant.id, message_id)
    items = []
    for row in rows:
        if row.citation_type == "database":
            items.append(
                DatabaseMessageCitation(
                    query_execution_id=row.query_execution_id,
                    table=row.title,
                    columns=[
                        str(item) for item in row.citation_metadata.get("columns", [])
                    ],
                )
            )
        elif row.file_id and row.chunk_id:
            file = await repository.get_file(
                context.tenant.id, row.file_id, include_deleted=True
            )
            if file is not None:
                items.append(
                    DocumentMessageCitation(
                        file_id=row.file_id,
                        chunk_id=row.chunk_id,
                        file_name=file.original_name,
                        page_number=row.page_number,
                        section_title=row.citation_metadata.get("section_title"),
                        sheet_name=row.citation_metadata.get("sheet_name"),
                        row_start=row.citation_metadata.get("row_start"),
                        row_end=row.citation_metadata.get("row_end"),
                        relevance_score=row.relevance_score,
                    )
                )
    return MessageCitationListResponse(items=items)
