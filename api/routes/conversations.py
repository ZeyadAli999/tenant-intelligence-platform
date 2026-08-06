"""Authenticated owner-scoped conversation APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from core.tenant_context import TenantContext, get_tenant_context
from schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
)
from services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    payload: ConversationCreateRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationResponse:
    return await ConversationService(session, context).create(payload)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationListResponse:
    return await ConversationService(session, context).list(page, page_size)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    message_page: Annotated[int, Query(ge=1)] = 1,
    message_page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationDetailResponse:
    return await ConversationService(session, context).detail(
        conversation_id, message_page, message_page_size
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await ConversationService(session, context).delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
