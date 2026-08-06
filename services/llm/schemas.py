"""Strict structured-output contracts and safe provider metadata."""

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSelectionContext(BaseModel):
    """Identifier-free, immutable routing metadata for classification only."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    database_sources_selected: bool = False
    document_sources_selected: bool = False
    database_source_count: int = Field(default=0, ge=0, le=10)
    document_source_count: int = Field(default=0, ge=0, le=100)


class RequestClassification(StructuredModel):
    intent: Literal["general", "database", "document", "hybrid", "clarification"]
    confidence: float = Field(ge=0, le=1)
    clarification_question: str | None = Field(default=None, max_length=500)
    short_reason: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_clarification(self) -> "RequestClassification":
        if self.intent == "clarification" and not self.clarification_question:
            raise ValueError("Clarification intent requires a question")
        if self.intent != "clarification" and self.clarification_question is not None:
            raise ValueError("Only clarification intent may include a question")
        return self


class SQLProposal(StructuredModel):
    action: Literal["generate_sql", "ask_clarification"]
    sql: str | None = Field(default=None, max_length=20000)
    clarification_question: str | None = Field(default=None, max_length=500)
    short_description: str = Field(min_length=1, max_length=300)
    proposed_tables: list[str] = Field(default_factory=list, max_length=30)
    proposed_columns: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_action(self) -> "SQLProposal":
        if self.action == "generate_sql":
            if not self.sql or self.clarification_question is not None:
                raise ValueError("SQL generation requires SQL and no clarification")
        elif self.sql is not None or not self.clarification_question:
            raise ValueError("Clarification requires a question and no SQL")
        return self


class GroundedAnswer(StructuredModel):
    answer: str = Field(min_length=1, max_length=10000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    result_summary_type: Literal[
        "scalar", "rows", "zero_rows", "truncated", "unavailable"
    ]


class DocumentQueryPlan(StructuredModel):
    search_query: str = Field(min_length=1, max_length=1000)
    key_terms: list[str] = Field(default_factory=list, max_length=20)
    answer_language: str = Field(min_length=2, max_length=40)
    short_reason: str = Field(min_length=1, max_length=120)


class DocumentGroundedAnswer(StructuredModel):
    answer: str = Field(min_length=1, max_length=10000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    used_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    insufficient_evidence: bool

    @model_validator(mode="after")
    def validate_evidence(self) -> "DocumentGroundedAnswer":
        if self.insufficient_evidence and self.used_evidence_ids:
            raise ValueError("Insufficient answers cannot cite evidence")
        if not self.insufficient_evidence and not self.used_evidence_ids:
            raise ValueError("Grounded answers require evidence")
        return self


class HybridGroundedAnswer(StructuredModel):
    answer: str = Field(min_length=1, max_length=10000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    used_evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    insufficient_evidence: bool

    @model_validator(mode="after")
    def validate_evidence(self) -> "HybridGroundedAnswer":
        if self.insufficient_evidence and self.used_evidence_ids:
            raise ValueError("Insufficient answers cannot cite evidence")
        if not self.insufficient_evidence and not self.used_evidence_ids:
            raise ValueError("Grounded answers require evidence")
        return self


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None


T = TypeVar("T", bound=StructuredModel)


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    value: T
    model: str
    usage: ProviderUsage = ProviderUsage()
    provider: str = "test-double"
