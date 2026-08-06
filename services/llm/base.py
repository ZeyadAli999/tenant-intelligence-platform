"""Abstract structured LLM provider contract."""

from abc import ABC, abstractmethod

from services.llm.schemas import (
    DocumentGroundedAnswer,
    DocumentQueryPlan,
    GroundedAnswer,
    HybridGroundedAnswer,
    ProviderResult,
    RequestClassification,
    SourceSelectionContext,
    SQLProposal,
)


class LLMProvider(ABC):
    @abstractmethod
    async def classify(
        self,
        question: str,
        history: tuple[str, ...],
        source_selection: SourceSelectionContext,
    ) -> ProviderResult[RequestClassification]: ...

    @abstractmethod
    async def propose_sql(
        self,
        question: str,
        schema: str,
        source_selection: SourceSelectionContext | None = None,
    ) -> ProviderResult[SQLProposal]: ...

    @abstractmethod
    async def repair_sql(
        self,
        question: str,
        schema: str,
        previous_sql: str,
        error_codes: tuple[str, ...],
    ) -> ProviderResult[SQLProposal]: ...

    @abstractmethod
    async def generate_answer(
        self, question: str, result: dict[str, object]
    ) -> ProviderResult[GroundedAnswer]: ...

    @abstractmethod
    async def rewrite_document_query(
        self, question: str, history: tuple[str, ...]
    ) -> ProviderResult[DocumentQueryPlan]: ...

    @abstractmethod
    async def generate_document_answer(
        self, question: str, evidence: dict[str, object]
    ) -> ProviderResult[DocumentGroundedAnswer]: ...

    @abstractmethod
    async def generate_hybrid_answer(
        self, question: str, evidence: dict[str, object]
    ) -> ProviderResult[HybridGroundedAnswer]: ...
