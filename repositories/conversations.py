"""Tenant-and-owner-scoped conversation persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Conversation, Message, QueryExecution


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self,
        tenant_id: UUID,
        user_id: UUID,
        conversation_id: UUID,
        *,
        active_only: bool = False,
    ) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
        )
        if active_only:
            statement = statement.where(Conversation.status == "active")
        return await self.session.scalar(statement)

    async def list(
        self, tenant_id: UUID, user_id: UUID, page: int, page_size: int
    ) -> tuple[list[Conversation], int]:
        where = (
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.status != "deleted",
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Conversation).where(*where)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(Conversation)
                    .where(*where)
                    .order_by(Conversation.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def messages(
        self, tenant_id: UUID, conversation_id: UUID, page: int, page_size: int
    ) -> tuple[list[Message], int]:
        where = (
            Message.tenant_id == tenant_id,
            Message.conversation_id == conversation_id,
        )
        total = await self.session.scalar(
            select(func.count()).select_from(Message).where(*where)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(Message)
                    .where(*where)
                    .order_by(Message.created_at)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def recent_messages(
        self,
        tenant_id: UUID,
        conversation_id: UUID,
        limit: int,
        *,
        exclude_ids: tuple[UUID, ...] = (),
    ) -> tuple[Message, ...]:
        statement = select(Message).where(
            Message.tenant_id == tenant_id,
            Message.conversation_id == conversation_id,
            Message.status.in_(("completed", "clarification")),
        )
        if exclude_ids:
            statement = statement.where(Message.id.not_in(exclude_ids))
        rows = list(
            (
                await self.session.scalars(
                    statement.order_by(Message.created_at.desc()).limit(limit)
                )
            ).all()
        )
        rows.reverse()
        return tuple(rows)

    async def message(
        self, tenant_id: UUID, user_id: UUID, message_id: UUID
    ) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .join(
                Conversation,
                (Conversation.id == Message.conversation_id)
                & (Conversation.tenant_id == Message.tenant_id),
            )
            .where(
                Message.id == message_id,
                Message.tenant_id == tenant_id,
                Conversation.user_id == user_id,
            )
        )

    async def execution_for_message(
        self, tenant_id: UUID, message_id: UUID
    ) -> QueryExecution | None:
        return await self.session.scalar(
            select(QueryExecution)
            .where(
                QueryExecution.tenant_id == tenant_id,
                QueryExecution.message_id == message_id,
            )
            .order_by(QueryExecution.created_at.desc())
        )
