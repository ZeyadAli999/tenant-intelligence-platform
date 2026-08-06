"""Owner-scoped database chat application service."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import DatabaseChatGraph
from agents.state import ChatState
from app.config import Settings
from app.exceptions import ApplicationError, ResourceNotFoundError
from core.tenant_context import TenantContext
from models import Message
from repositories.conversations import ConversationRepository
from repositories.database_connections import DatabaseConnectionRepository
from repositories.documents import DocumentRepository
from schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatUsage,
    DatabaseCitation,
    DocumentCitation,
    MessageSQLResponse,
    SafeSQLInfo,
)
from services.documents.access_policy import KnowledgeBaseAccessPolicy
from services.documents.embeddings import EmbeddingService
from services.llm.base import LLMProvider
from services.llm.schemas import SourceSelectionContext

logger = logging.getLogger(__name__)


class ChatProcessingError(ApplicationError):
    detail = "Chat request could not be completed"


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        context: TenantContext,
        provider: LLMProvider,
        settings: Settings,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.provider = provider
        self.settings = settings
        self.repository = ConversationRepository(session)
        self.embeddings = embeddings

    async def prepare(self, payload: ChatRequest) -> ChatState:
        conversation = await self.repository.get(
            self.context.tenant.id,
            self.context.user.id,
            payload.conversation_id,
            active_only=True,
        )
        if conversation is None:
            raise ResourceNotFoundError
        if len(payload.message) > self.settings.chat_max_message_length:
            raise ChatProcessingError
        requested = payload.database_connection_ids or [
            UUID(str(item)) for item in conversation.active_connection_ids
        ]
        if len(requested) > 1:
            raise ChatProcessingError
        connection_id = requested[0] if requested else None
        requested_kbs = payload.knowledge_base_ids or [
            UUID(str(item)) for item in conversation.active_knowledge_base_ids
        ]
        await KnowledgeBaseAccessPolicy(
            DocumentRepository(self.session), self.context
        ).require_many(requested_kbs, active=True)
        if connection_id is not None:
            connection = await DatabaseConnectionRepository(
                self.session
            ).get_connection(self.context.tenant.id, connection_id)
            if (
                connection is None
                or not connection.is_active
                or connection.status != "connected"
            ):
                raise ResourceNotFoundError
        user_message = Message(
            id=uuid4(),
            tenant_id=self.context.tenant.id,
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
            status="completed",
        )
        assistant_message = Message(
            id=uuid4(),
            tenant_id=self.context.tenant.id,
            conversation_id=conversation.id,
            parent_message_id=user_message.id,
            role="assistant",
            content="Processing request",
            status="pending",
        )
        conversation.last_message_at = datetime.now(UTC)
        self.session.add(user_message)
        await self.session.flush()
        self.session.add(assistant_message)
        await self.session.commit()
        return ChatState(
            tenant_id=self.context.tenant.id,
            user_id=self.context.user.id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            question=payload.message,
            connection_id=connection_id,
            knowledge_base_ids=tuple(requested_kbs),
            source_selection=SourceSelectionContext(
                database_sources_selected=connection_id is not None,
                document_sources_selected=bool(requested_kbs),
                database_source_count=int(connection_id is not None),
                document_source_count=len(requested_kbs),
            ),
        )

    async def run(self, payload: ChatRequest) -> ChatResponse:
        try:
            state = await self.prepare(payload)
            final = await DatabaseChatGraph(
                self.session,
                self.context,
                self.provider,
                self.settings,
                embeddings=self.embeddings,
            ).run(state)
        except ApplicationError:
            raise
        except Exception as exc:
            logger.error("Chat processing failed exception_type=%s", type(exc).__name__)
            if "state" in locals():
                await self._mark_failed(state["assistant_message_id"])
            raise ChatProcessingError from exc
        return self.response(final)

    async def stream(
        self, payload: ChatRequest
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        state = await self.prepare(payload)
        accumulated: ChatState = dict(state)
        try:
            yield (
                "started",
                {
                    "conversation_id": str(state["conversation_id"]),
                    "message_id": str(state["assistant_message_id"]),
                },
            )
            graph = DatabaseChatGraph(
                self.session,
                self.context,
                self.provider,
                self.settings,
                self.embeddings,
            )
            async for node, update in graph.stream(state):
                if update:
                    accumulated.update(update)
                for event in self._public_events(node, accumulated):
                    yield event
            yield "completed", self.response(accumulated).model_dump(mode="json")
        except asyncio.CancelledError:
            await asyncio.shield(self._mark_cancelled(state["assistant_message_id"]))
            raise
        except GeneratorExit:
            await asyncio.shield(self._mark_cancelled(state["assistant_message_id"]))
            raise
        except Exception as exc:  # noqa: BLE001 -- streaming must emit one sanitized terminal event
            logger.error("Chat stream failed exception_type=%s", type(exc).__name__)
            await self._mark_failed(state["assistant_message_id"])
            yield "error", {"detail": "Chat request could not be completed"}

    def response(self, state: ChatState) -> ChatResponse:
        classification = state.get("classification")
        intent = classification.intent if classification else "clarification"
        query_id = state.get("query_execution_id")
        sql = None
        if query_id and state.get("safe_normalized_sql"):
            sql = SafeSQLInfo(
                query_execution_id=query_id,
                normalized_sql=state["safe_normalized_sql"],
                row_count=state.get("row_count", 0),
                truncated=state.get("truncated", False),
            )
        tables = list(state.get("referenced_tables", ()))
        document_citations = [
            DocumentCitation.model_validate(item)
            for item in state.get("document_citations", ())
        ]
        return ChatResponse(
            conversation_id=state["conversation_id"],
            message_id=state["assistant_message_id"],
            answer=state.get("answer", "The request could not be completed safely."),
            intent=intent,
            sources_used=list(state.get("sources_used", ())),
            sql=sql,
            citations=[
                DatabaseCitation(table=table, query_execution_id=query_id)
                for table in tables
            ]
            + document_citations,
            warnings=list(state.get("warnings", ())),
            usage=ChatUsage(
                prompt_tokens=state.get("prompt_tokens", 0),
                completion_tokens=state.get("completion_tokens", 0),
                provider_latency_ms=state.get("latency_ms", 0),
            ),
        )

    async def message_sql(self, message_id: UUID) -> MessageSQLResponse:
        message = await self.repository.message(
            self.context.tenant.id, self.context.user.id, message_id
        )
        if message is None:
            raise ResourceNotFoundError
        execution = await self.repository.execution_for_message(
            self.context.tenant.id, message_id
        )
        if execution is None or not execution.normalized_sql:
            raise ResourceNotFoundError
        return MessageSQLResponse(
            message_id=message.id,
            query_execution_id=execution.id,
            normalized_sql=execution.normalized_sql,
            execution_status=execution.execution_status,
            row_count=execution.returned_row_count,
            truncated=execution.result_truncated,
            referenced_tables=[str(item) for item in execution.referenced_tables],
        )

    async def _mark_failed(self, message_id: UUID) -> None:
        await self.session.rollback()
        message = await self.repository.message(
            self.context.tenant.id, self.context.user.id, message_id
        )
        if message is not None:
            message.status = "failed"
            message.content = "The chat request could not be completed safely."
            message.error_message = "Chat processing failed safely"
            await self.session.commit()

    async def _mark_cancelled(self, message_id: UUID) -> None:
        await self.session.rollback()
        message = await self.repository.message(
            self.context.tenant.id, self.context.user.id, message_id
        )
        if message is not None and message.status == "pending":
            message.status = "cancelled"
            message.content = "The streaming request was cancelled."
            message.error_message = "Chat processing cancelled safely"
            await self.session.commit()

    @staticmethod
    def _public_events(
        node: str, state: ChatState
    ) -> tuple[tuple[str, dict[str, object]], ...]:
        if node == "classify_request":
            return (("classified", {"intent": state["classification"].intent}),)
        if node == "validate_execute" and state.get("safe_normalized_sql"):
            return (
                ("query_validated", {"normalized_sql": state["safe_normalized_sql"]}),
                (
                    "query_executed",
                    {
                        "row_count": state.get("row_count", 0),
                        "truncated": state.get("truncated", False),
                    },
                ),
            )
        if node == "clarification_answer":
            return (("clarification", {"text": state.get("answer", "")}),)
        if node in {
            "generate_answer",
            "general_answer",
            "unsupported_answer",
            "generate_document_answer",
        }:
            answer = state.get("answer", "")
            return tuple(
                ("answer_delta", {"text": answer[index : index + 32]})
                for index in range(0, len(answer), 32)
            )
        if node == "hybrid_chat":
            prefix: tuple[tuple[str, dict[str, object]], ...] = ()
            if state.get("safe_normalized_sql"):
                prefix = (
                    (
                        "query_validated",
                        {"normalized_sql": state["safe_normalized_sql"]},
                    ),
                    (
                        "query_executed",
                        {
                            "row_count": state.get("row_count", 0),
                            "truncated": state.get("truncated", False),
                        },
                    ),
                )
            answer = state.get("answer", "")
            return prefix + tuple(
                ("answer_delta", {"text": answer[index : index + 32]})
                for index in range(0, len(answer), 32)
            )
        return ()
