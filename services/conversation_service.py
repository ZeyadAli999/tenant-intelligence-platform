"""Owner-scoped conversation lifecycle."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidPermissionError, ResourceNotFoundError
from core.tenant_context import TenantContext
from models import Conversation, Message
from repositories.conversations import ConversationRepository
from repositories.database_connections import DatabaseConnectionRepository
from repositories.documents import DocumentRepository
from schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)
from services.documents.access_policy import KnowledgeBaseAccessPolicy


class ConversationService:
    def __init__(self, session: AsyncSession, context: TenantContext) -> None:
        self.session = session
        self.context = context
        self.repository = ConversationRepository(session)

    async def create(self, payload: ConversationCreateRequest) -> ConversationResponse:
        document_policy = KnowledgeBaseAccessPolicy(
            DocumentRepository(self.session), self.context
        )
        for knowledge_base_id in payload.knowledge_base_ids:
            await document_policy.require(knowledge_base_id, active=True)
        for connection_id in payload.database_connection_ids:
            connection = await DatabaseConnectionRepository(
                self.session
            ).get_connection(self.context.tenant.id, connection_id)
            if (
                connection is None
                or not connection.is_active
                or connection.status != "connected"
            ):
                raise InvalidPermissionError
        conversation = Conversation(
            id=uuid4(),
            tenant_id=self.context.tenant.id,
            user_id=self.context.user.id,
            title=payload.title.strip() if payload.title else None,
            active_connection_ids=[
                str(item) for item in payload.database_connection_ids
            ],
            active_knowledge_base_ids=[
                str(item) for item in payload.knowledge_base_ids
            ],
            settings={},
        )
        self.session.add(conversation)
        await self.session.commit()
        return self.response(conversation)

    async def list(self, page: int, page_size: int) -> ConversationListResponse:
        rows, total = await self.repository.list(
            self.context.tenant.id, self.context.user.id, page, page_size
        )
        return ConversationListResponse(
            items=[self.response(item) for item in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def detail(
        self, conversation_id: UUID, message_page: int, message_page_size: int
    ) -> ConversationDetailResponse:
        conversation = await self._get(conversation_id)
        messages, total = await self.repository.messages(
            self.context.tenant.id, conversation.id, message_page, message_page_size
        )
        base = self.response(conversation).model_dump()
        return ConversationDetailResponse(
            **base,
            messages=[self.message_response(item) for item in messages],
            message_total=total,
            message_page=message_page,
            message_page_size=message_page_size,
        )

    async def delete(self, conversation_id: UUID) -> None:
        conversation = await self._get(conversation_id)
        conversation.status = "deleted"
        await self.session.commit()

    async def _get(
        self, conversation_id: UUID, *, active_only: bool = False
    ) -> Conversation:
        row = await self.repository.get(
            self.context.tenant.id,
            self.context.user.id,
            conversation_id,
            active_only=active_only,
        )
        if row is None or row.status == "deleted":
            raise ResourceNotFoundError
        return row

    @staticmethod
    def response(row: Conversation) -> ConversationResponse:
        return ConversationResponse(
            id=row.id,
            title=row.title,
            status=row.status,
            database_connection_ids=[
                UUID(str(item)) for item in row.active_connection_ids
            ],
            knowledge_base_ids=[
                UUID(str(item)) for item in row.active_knowledge_base_ids
            ],
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
        )

    @staticmethod
    def message_response(row: Message) -> MessageResponse:
        structured = row.structured_content
        warnings = (
            structured.get("warnings", []) if isinstance(structured, dict) else []
        )
        return MessageResponse(
            id=row.id,
            parent_message_id=row.parent_message_id,
            role=row.role,
            message_type=row.message_type,
            content=row.content,
            detected_intent=row.detected_intent,
            selected_sources=row.selected_sources,
            status=row.status,
            model_name=row.model_name,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            latency_ms=row.latency_ms,
            warnings=[str(item) for item in warnings]
            if isinstance(warnings, list)
            else [],
            created_at=row.created_at,
        )
