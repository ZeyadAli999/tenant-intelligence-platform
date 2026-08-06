"""LangGraph database-only chat orchestrator with deterministic security nodes."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from agents.state import ChatState
from app.config import Settings
from core.tenant_context import TenantContext
from models import MessageCitation, StoredFile
from repositories.conversations import ConversationRepository
from services.database.permission_resolver import PermissionResolver
from services.database.query_executor import SafeQueryRejectedError, SafeQueryService
from services.database.schema_retriever import AllowedSchemaRetriever
from services.documents.embeddings import EmbeddingService, FastEmbedService
from services.documents.retrieval import DocumentRetrievalService
from services.llm.base import LLMProvider
from services.llm.schemas import RequestClassification, SourceSelectionContext

SAFE_REPAIR_CODES = {"INVALID_SQL"}


class DatabaseChatGraph:
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
        self.embeddings = embeddings
        self.repository = ConversationRepository(session)
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(ChatState)
        for name, node in (
            ("load_context", self.load_context),
            ("classify_request", self.classify_request),
            ("select_source", self.select_source),
            ("retrieve_schema", self.retrieve_schema),
            ("generate_sql", self.generate_sql),
            ("validate_execute", self.validate_execute),
            ("repair_sql", self.repair_sql),
            ("generate_answer", self.generate_answer),
            ("general_answer", self.general_answer),
            ("unsupported_answer", self.unsupported_answer),
            ("clarification_answer", self.clarification_answer),
            ("select_document_source", self.select_document_source),
            ("rewrite_document_query", self.rewrite_document_query),
            ("retrieve_documents", self.retrieve_documents),
            ("generate_document_answer", self.generate_document_answer),
            ("hybrid_chat", self.hybrid_chat),
            ("persist_result", self.persist_result),
        ):
            builder.add_node(name, node)
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "classify_request")
        builder.add_conditional_edges(
            "classify_request",
            self.route_intent,
            {
                "database": "select_source",
                "document": "select_document_source",
                "hybrid": "hybrid_chat",
                "general": "general_answer",
                "unsupported": "unsupported_answer",
                "clarification": "clarification_answer",
            },
        )
        builder.add_edge("select_source", "retrieve_schema")
        builder.add_conditional_edges(
            "select_document_source",
            lambda state: "retrieve" if state.get("knowledge_base_ids") else "clarify",
            {"retrieve": "rewrite_document_query", "clarify": "clarification_answer"},
        )
        builder.add_edge("rewrite_document_query", "retrieve_documents")
        builder.add_edge("retrieve_documents", "generate_document_answer")
        builder.add_conditional_edges(
            "retrieve_schema",
            lambda state: "generate" if state.get("compact_schema") else "clarify",
            {"generate": "generate_sql", "clarify": "clarification_answer"},
        )
        builder.add_conditional_edges(
            "generate_sql",
            lambda state: (
                "execute"
                if state["sql_proposal"].action == "generate_sql"
                else "clarify"
            ),
            {"execute": "validate_execute", "clarify": "clarification_answer"},
        )
        builder.add_conditional_edges(
            "validate_execute",
            self.route_execution,
            {
                "answer": "generate_answer",
                "repair": "repair_sql",
                "failed": "persist_result",
            },
        )
        builder.add_edge("repair_sql", "validate_execute")
        for node in (
            "generate_answer",
            "general_answer",
            "unsupported_answer",
            "clarification_answer",
            "generate_document_answer",
            "hybrid_chat",
        ):
            builder.add_edge(node, "persist_result")
        builder.add_edge("persist_result", END)
        return builder.compile()

    async def run(self, state: ChatState) -> ChatState:
        return await self.graph.ainvoke(
            state, config={"recursion_limit": self.settings.chat_graph_recursion_limit}
        )

    async def stream(self, state: ChatState) -> AsyncIterator[tuple[str, ChatState]]:
        async for update in self.graph.astream(
            state,
            config={"recursion_limit": self.settings.chat_graph_recursion_limit},
            stream_mode="updates",
        ):
            for node, values in update.items():
                yield node, values

    async def load_context(self, state: ChatState) -> ChatState:
        recent = await self.repository.recent_messages(
            state["tenant_id"],
            state["conversation_id"],
            self.settings.chat_history_messages,
            exclude_ids=(state["user_message_id"], state["assistant_message_id"]),
        )
        return {
            "safe_history": tuple(
                f"{item.role}: {item.content[:1000]}" for item in recent
            ),
            "repair_count": 0,
        }

    async def classify_request(self, state: ChatState) -> ChatState:
        result = await self.provider.classify(
            state["question"],
            state.get("safe_history", ()),
            state.get("source_selection", SourceSelectionContext()),
        )
        model_classification = result.value
        classification = self.resolve_classification(
            model_classification,
            state.get("source_selection", SourceSelectionContext()),
        )
        return {
            "classification": classification,
            "model_classified_intent": model_classification.intent,
            "resolved_executable_intent": classification.intent,
            **self._usage(state, result, "classification"),
        }

    @staticmethod
    def resolve_classification(
        classification: RequestClassification,
        selection: SourceSelectionContext,
    ) -> RequestClassification:
        if selection.database_sources_selected and selection.document_sources_selected:
            resolved = "hybrid"
        elif selection.document_sources_selected:
            resolved = "document"
        elif selection.database_sources_selected:
            resolved = "database"
        else:
            if classification.intent in {"database", "document", "hybrid"}:
                return RequestClassification(
                    intent="clarification",
                    confidence=classification.confidence,
                    clarification_question="Which authorized source should I use?",
                    short_reason="required source selection missing",
                )
            if (
                classification.confidence < 0.6
                and classification.intent != "clarification"
            ):
                return RequestClassification(
                    intent="clarification",
                    confidence=classification.confidence,
                    clarification_question="Could you clarify your request?",
                    short_reason="low confidence",
                )
            return classification
        return RequestClassification(
            intent=resolved,
            confidence=classification.confidence,
            clarification_question=None,
            short_reason="explicit selected source categories",
        )

    @staticmethod
    def route_intent(
        state: ChatState,
    ) -> Literal[
        "database", "document", "hybrid", "general", "unsupported", "clarification"
    ]:
        intent = state.get("resolved_executable_intent", state["classification"].intent)
        if intent == "database":
            return "database"
        if intent == "general":
            return "general"
        if intent == "document":
            return "document"
        if intent == "hybrid":
            return "hybrid"
        return "clarification"

    async def select_source(self, state: ChatState) -> ChatState:
        if state.get("connection_id") is None:
            return {
                "compact_schema": "",
                "answer": "Which single active database connection should I use?",
                "status": "clarification",
            }
        return {}

    async def select_document_source(self, state: ChatState) -> ChatState:
        if not state.get("knowledge_base_ids"):
            return {
                "answer": "Which authorized knowledge base should I search?",
                "status": "clarification",
            }
        return {}

    async def rewrite_document_query(self, state: ChatState) -> ChatState:
        result = await self.provider.rewrite_document_query(
            state["question"], state.get("safe_history", ())
        )
        return {
            "document_query": result.value.search_query,
            **self._usage(state, result, "document_query_rewrite"),
        }

    async def retrieve_documents(self, state: ChatState) -> ChatState:
        embeddings = self.embeddings or FastEmbedService(self.settings)
        evidence = await DocumentRetrievalService(
            self.session, self.settings, embeddings
        ).retrieve(
            state["tenant_id"],
            list(state["knowledge_base_ids"]),
            state["document_query"],
        )
        return {"document_evidence": evidence}

    async def generate_document_answer(self, state: ChatState) -> ChatState:
        evidence = state.get("document_evidence", ())
        if not evidence:
            return {
                "answer": "I could not find sufficient authorized document evidence.",
                "warnings": ("Insufficient document evidence.",),
                "sources_used": (),
                "document_citations": (),
                "status": "completed",
            }
        payload = {
            "evidence": [
                {
                    "id": item.evidence_id,
                    "text": item.chunk.content,
                    "page_number": item.chunk.page_number,
                    "section_title": item.chunk.section_title,
                    "sheet_name": item.chunk.sheet_name,
                    "row_start": item.chunk.row_start,
                    "row_end": item.chunk.row_end,
                }
                for item in evidence
            ]
        }
        result = await self.provider.generate_document_answer(
            state["question"], payload
        )
        allowed = {item.evidence_id: item for item in evidence}
        cited_ids = result.value.used_evidence_ids
        if any(item not in allowed for item in cited_ids):
            return {
                "answer": "The document answer could not be grounded safely.",
                "warnings": ("Invalid document citation rejected.",),
                "sources_used": (),
                "document_citations": (),
                "status": "failed",
                **self._usage(state, result, "document_answer_generation"),
            }
        citations: list[dict[str, object]] = []
        for evidence_id in dict.fromkeys(cited_ids):
            item = allowed[evidence_id]
            file = await self.session.get(StoredFile, item.chunk.file_id)
            if file is None or file.tenant_id != state["tenant_id"]:
                continue
            citations.append(
                {
                    "type": "document",
                    "file_id": file.id,
                    "chunk_id": item.chunk.id,
                    "file_name": file.original_name,
                    "page_number": item.chunk.page_number,
                    "section_title": item.chunk.section_title,
                    "sheet_name": item.chunk.sheet_name,
                    "row_start": item.chunk.row_start,
                    "row_end": item.chunk.row_end,
                    "relevance_score": item.score,
                }
            )
        sources = ("documents",) if citations else ()
        return {
            "answer": result.value.answer,
            "warnings": tuple(result.value.warnings),
            "sources_used": sources,
            "document_citations": tuple(citations),
            "status": "completed",
            **self._usage(state, result, "document_answer_generation"),
        }

    async def hybrid_chat(self, state: ChatState) -> ChatState:
        """Run both deterministic safety branches, then merge approved evidence."""

        if state.get("connection_id") is None or not state.get("knowledge_base_ids"):
            return {
                "answer": "Which active database connection and authorized knowledge base should I use?",
                "warnings": (),
                "sources_used": (),
                "status": "clarification",
            }
        current: ChatState = dict(state)
        for operation in (
            self.retrieve_schema,
            self.generate_sql,
            self.validate_execute,
            self.rewrite_document_query,
            self.retrieve_documents,
        ):
            update = await operation(current)
            current.update(update)
            if operation == self.retrieve_schema and not current.get("compact_schema"):
                return update
            if (
                operation == self.generate_sql
                and current["sql_proposal"].action != "generate_sql"
            ):
                return {
                    **update,
                    "answer": current["sql_proposal"].clarification_question,
                    "status": "clarification",
                }

        evidence: list[dict[str, object]] = []
        if current.get("masked_rows") is not None:
            evidence.append(
                {
                    "id": "DB1",
                    "kind": "database",
                    "columns": current.get("approved_columns", ()),
                    "rows": current.get("masked_rows", ()),
                    "row_count": current.get("row_count", 0),
                    "truncated": current.get("truncated", False),
                }
            )
        for item in current.get("document_evidence", ()):
            evidence.append(
                {
                    "id": item.evidence_id,
                    "kind": "document",
                    "text": item.chunk.content,
                    "page_number": item.chunk.page_number,
                    "section_title": item.chunk.section_title,
                    "sheet_name": item.chunk.sheet_name,
                    "row_start": item.chunk.row_start,
                    "row_end": item.chunk.row_end,
                }
            )
        if not evidence:
            return {
                **current,
                "answer": "I could not find sufficient authorized database or document evidence.",
                "warnings": ("Insufficient hybrid evidence.",),
                "sources_used": (),
                "status": "completed",
            }
        result = await self.provider.generate_hybrid_answer(
            state["question"], {"evidence": evidence}
        )
        allowed_ids = {str(item["id"]) for item in evidence}
        cited = tuple(dict.fromkeys(result.value.used_evidence_ids))
        if any(item not in allowed_ids for item in cited):
            return {
                **current,
                "answer": "The hybrid answer could not be grounded safely.",
                "warnings": ("Invalid hybrid citation rejected.",),
                "sources_used": (),
                "document_citations": (),
                "status": "failed",
                **self._usage(current, result, "hybrid_answer_generation"),
            }
        document_state = await self._document_citations(
            current, tuple(item for item in cited if item.startswith("DOC"))
        )
        sources: list[str] = []
        if "DB1" in cited and current.get("query_execution_id"):
            sources.append("database")
        else:
            current["referenced_tables"] = ()
        if document_state["document_citations"]:
            sources.append("documents")
        return {
            **current,
            **document_state,
            "answer": result.value.answer,
            "warnings": tuple(result.value.warnings),
            "sources_used": tuple(sources),
            "status": "completed",
            **self._usage(current, result, "hybrid_answer_generation"),
        }

    async def _document_citations(
        self, state: ChatState, cited_ids: tuple[str, ...]
    ) -> ChatState:
        allowed = {
            item.evidence_id: item for item in state.get("document_evidence", ())
        }
        citations: list[dict[str, object]] = []
        for evidence_id in cited_ids:
            item = allowed.get(evidence_id)
            if item is None:
                continue
            file = await self.session.get(StoredFile, item.chunk.file_id)
            if file is None or file.tenant_id != state["tenant_id"]:
                continue
            citations.append(
                {
                    "type": "document",
                    "file_id": file.id,
                    "chunk_id": item.chunk.id,
                    "file_name": file.original_name,
                    "page_number": item.chunk.page_number,
                    "section_title": item.chunk.section_title,
                    "sheet_name": item.chunk.sheet_name,
                    "row_start": item.chunk.row_start,
                    "row_end": item.chunk.row_end,
                    "relevance_score": item.score,
                }
            )
        return {"document_citations": tuple(citations)}

    async def retrieve_schema(self, state: ChatState) -> ChatState:
        if state.get("connection_id") is None:
            return {"compact_schema": ""}
        allowed = await PermissionResolver(self.session).resolve(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            role_ids=tuple(role.id for role in self.context.roles),
            connection_id=state["connection_id"],
        )
        selected = AllowedSchemaRetriever(
            self.settings.llm_schema_max_tables, self.settings.llm_schema_max_columns
        ).retrieve(state["question"], allowed)
        if selected is None:
            return {
                "compact_schema": "",
                "answer": "Could you clarify the approved database table or field you want to query?",
                "status": "clarification",
            }
        return {
            "compact_schema": selected.serialized,
            "visible_tables": selected.table_names,
        }

    async def generate_sql(self, state: ChatState) -> ChatState:
        result = await self.provider.propose_sql(
            state["question"],
            state["compact_schema"],
            state.get("source_selection", SourceSelectionContext()),
        )
        return {
            "sql_proposal": result.value,
            **self._usage(state, result, "sql_proposal"),
        }

    async def validate_execute(self, state: ChatState) -> ChatState:
        proposal = state["sql_proposal"]
        try:
            result = await SafeQueryService(
                self.session, settings=self.settings
            ).execute(
                self.context,
                state["connection_id"],  # type: ignore[arg-type]
                proposal.sql or "",
                request_id=f"chat-{state['assistant_message_id']}",
                conversation_id=state["conversation_id"],
                message_id=state["assistant_message_id"],
            )
            return {
                "query_execution_id": result.query_execution_id,
                "safe_normalized_sql": result.normalized_query,
                "approved_columns": result.columns,
                "masked_rows": result.rows,
                "row_count": result.row_count,
                "truncated": result.truncated,
                "referenced_tables": result.referenced_tables,
                "sources_used": ("database",),
                "status": "completed",
                "safe_error_codes": (),
            }
        except SafeQueryRejectedError:
            execution = await self.repository.execution_for_message(
                state["tenant_id"], state["assistant_message_id"]
            )
            codes = tuple(
                item.get("code", "QUERY_REJECTED")
                for item in (execution.validation_errors if execution else [])
            )
            return {
                "safe_error_codes": codes or ("QUERY_REJECTED",),
                "query_execution_id": execution.id if execution else None,
                "answer": "The proposed database query could not be executed safely.",
                "warnings": ("Query rejected by the safety boundary.",),
                "status": "failed",
            }

    @staticmethod
    def route_execution(state: ChatState) -> Literal["answer", "repair", "failed"]:
        if state.get("masked_rows") is not None:
            return "answer"
        codes = set(state.get("safe_error_codes", ()))
        if state.get("repair_count", 0) == 0 and codes and codes <= SAFE_REPAIR_CODES:
            return "repair"
        return "failed"

    async def repair_sql(self, state: ChatState) -> ChatState:
        result = await self.provider.repair_sql(
            state["question"],
            state["compact_schema"],
            state["sql_proposal"].sql or "",
            state.get("safe_error_codes", ()),
        )
        return {
            "sql_proposal": result.value,
            "repair_count": 1,
            **self._usage(state, result, "sql_repair"),
        }

    async def generate_answer(self, state: ChatState) -> ChatState:
        rows = state.get("masked_rows", ())
        if not rows:
            return {
                "answer": "No matching rows were returned.",
                "warnings": (),
                "status": "completed",
            }
        if len(rows) == 1 and len(rows[0]) == 1:
            name, value = next(iter(rows[0].items()))
            return {
                "answer": f"{name}: {value}",
                "warnings": ("Results were truncated.",)
                if state.get("truncated")
                else (),
                "status": "completed",
            }
        approved = {
            "columns": state.get("approved_columns", ()),
            "rows": rows,
            "row_count": state.get("row_count", 0),
            "truncated": state.get("truncated", False),
            "source_labels": state.get("referenced_tables", ()),
        }
        result = await self.provider.generate_answer(state["question"], approved)
        return {
            "answer": result.value.answer,
            "warnings": tuple(result.value.warnings),
            "status": "completed",
            **self._usage(state, result, "answer_generation"),
        }

    async def general_answer(self, state: ChatState) -> ChatState:
        return {
            "answer": "I can answer general capability questions and query one authorized database connection using the approved schema and safety boundary.",
            "warnings": (),
            "sources_used": (),
            "status": "completed",
        }

    async def unsupported_answer(self, state: ChatState) -> ChatState:
        return {
            "answer": "This request is outside the supported database and document capabilities.",
            "warnings": ("No approved source was accessed.",),
            "sources_used": (),
            "status": "completed",
        }

    async def clarification_answer(self, state: ChatState) -> ChatState:
        question = (
            state.get("answer")
            or state.get("sql_proposal", None)
            and state["sql_proposal"].clarification_question
            or state["classification"].clarification_question
            or "Could you clarify your database question?"
        )
        return {
            "answer": str(question),
            "warnings": (),
            "sources_used": (),
            "status": "clarification",
        }

    async def persist_result(self, state: ChatState) -> ChatState:
        message = await self.repository.message(
            state["tenant_id"], state["user_id"], state["assistant_message_id"]
        )
        conversation = await self.repository.get(
            state["tenant_id"], state["user_id"], state["conversation_id"]
        )
        if message is None or conversation is None:
            return {
                "status": "failed",
                "answer": "The chat result could not be persisted safely.",
            }
        classification = state["classification"]
        message.content = state.get(
            "answer", "The request could not be completed safely."
        )
        message.message_type = (
            "database" if classification.intent == "database" else classification.intent
        )
        message.detected_intent = classification.intent
        message.selected_sources = list(state.get("sources_used", ()))
        message.model_name = state.get("model_name")
        message.prompt_version = "phase3c_v1"
        message.prompt_tokens = state.get("prompt_tokens")
        message.completion_tokens = state.get("completion_tokens")
        message.latency_ms = state.get("latency_ms")
        message.status = state.get("status", "failed")
        message.error_message = (
            "Chat processing failed safely" if message.status == "failed" else None
        )
        message.structured_content = {
            "warnings": list(state.get("warnings", ())),
            "query_execution_id": str(state["query_execution_id"])
            if state.get("query_execution_id")
            else None,
            "prompt_version": "phase3c_v1",
            "provider": state.get("provider_name"),
            "provider_usage_by_stage": state.get("usage_by_stage", {}),
        }
        for citation in state.get("document_citations", ()):
            self.session.add(
                MessageCitation(
                    tenant_id=state["tenant_id"],
                    message_id=message.id,
                    citation_type="document",
                    file_id=citation["file_id"],
                    chunk_id=citation["chunk_id"],
                    title=str(citation["file_name"]),
                    source_reference="document evidence",
                    page_number=citation.get("page_number"),
                    relevance_score=citation.get("relevance_score"),
                    citation_metadata={
                        key: citation.get(key)
                        for key in (
                            "section_title",
                            "sheet_name",
                            "row_start",
                            "row_end",
                        )
                    },
                )
            )
        if state.get("query_execution_id"):
            for table in state.get("referenced_tables", ()):
                self.session.add(
                    MessageCitation(
                        tenant_id=state["tenant_id"],
                        message_id=message.id,
                        citation_type="database",
                        query_execution_id=state["query_execution_id"],
                        title=str(table),
                        source_reference="validated query execution",
                        citation_metadata={
                            "columns": list(state.get("approved_columns", ()))
                        },
                    )
                )
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        return {}

    @staticmethod
    def _usage(state: ChatState, result, stage: str) -> ChatState:
        prompt = result.usage.prompt_tokens or 0
        completion = result.usage.completion_tokens or 0
        latency = result.usage.latency_ms or 0
        by_stage = dict(state.get("usage_by_stage", {}))
        by_stage[stage] = {
            "provider": result.provider,
            "model": result.model,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "latency_ms": latency,
        }
        return {
            "provider_name": result.provider,
            "model_name": result.model,
            "prompt_tokens": state.get("prompt_tokens", 0) + prompt,
            "completion_tokens": state.get("completion_tokens", 0) + completion,
            "latency_ms": state.get("latency_ms", 0) + latency,
            "usage_by_stage": by_stage,
        }
