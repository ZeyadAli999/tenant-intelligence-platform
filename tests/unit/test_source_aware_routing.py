"""Provider-independent source-aware executable intent regressions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agents.graph import DatabaseChatGraph
from services.llm.fake_provider import FakeLLMProvider
from services.llm.schemas import (
    ProviderResult,
    RequestClassification,
    SourceSelectionContext,
)

SMOKE_QUESTION = "What are the refund and contract notice policies?"


def classified(intent: str, confidence: float = 0.99) -> RequestClassification:
    if intent == "clarification":
        return RequestClassification(
            intent=intent,
            confidence=confidence,
            clarification_question="Which source should I use?",
            short_reason="clarification",
        )
    return RequestClassification(
        intent=intent, confidence=confidence, short_reason="model classification"
    )


@pytest.mark.parametrize(
    ("selection", "model_intent", "expected"),
    [
        (
            SourceSelectionContext(
                document_sources_selected=True, document_source_count=1
            ),
            "general",
            "document",
        ),
        (
            SourceSelectionContext(
                database_sources_selected=True, database_source_count=1
            ),
            "general",
            "database",
        ),
        (
            SourceSelectionContext(
                database_sources_selected=True,
                document_sources_selected=True,
                database_source_count=1,
                document_source_count=1,
            ),
            "general",
            "hybrid",
        ),
        (SourceSelectionContext(), "general", "general"),
        (SourceSelectionContext(), "database", "clarification"),
        (SourceSelectionContext(), "document", "clarification"),
        (SourceSelectionContext(), "hybrid", "clarification"),
    ],
)
def test_deterministic_source_selection_policy(
    selection, model_intent, expected
) -> None:
    resolved = DatabaseChatGraph.resolve_classification(
        classified(model_intent), selection
    )
    assert resolved.intent == expected


def test_low_confidence_only_clarifies_when_no_source_is_selected() -> None:
    low = classified("general", 0.2)
    assert (
        DatabaseChatGraph.resolve_classification(low, SourceSelectionContext()).intent
        == "clarification"
    )
    selected = SourceSelectionContext(
        document_sources_selected=True, document_source_count=1
    )
    assert DatabaseChatGraph.resolve_classification(low, selected).intent == "document"


@pytest.mark.asyncio
async def test_exact_smoke_question_resolves_to_document_when_model_says_general() -> (
    None
):
    class GeneralProvider(FakeLLMProvider):
        async def classify(self, question, history, source_selection):
            assert question == SMOKE_QUESTION
            assert source_selection.document_sources_selected
            return ProviderResult(classified("general"), self.model)

    graph = object.__new__(DatabaseChatGraph)
    graph.provider = GeneralProvider()
    result = await graph.classify_request(
        {
            "question": SMOKE_QUESTION,
            "safe_history": (),
            "source_selection": SourceSelectionContext(
                document_sources_selected=True, document_source_count=1
            ),
        }
    )
    assert result["model_classified_intent"] == "general"
    assert result["resolved_executable_intent"] == "document"
    assert result["classification"].intent == "document"


def test_source_selection_context_is_identifier_free_immutable_and_bounded() -> None:
    assert set(SourceSelectionContext.model_fields) == {
        "database_sources_selected",
        "document_sources_selected",
        "database_source_count",
        "document_source_count",
    }
    context = SourceSelectionContext(
        document_sources_selected=True, document_source_count=1
    )
    with pytest.raises(ValidationError):
        context.document_source_count = 2
    with pytest.raises(ValidationError):
        SourceSelectionContext(document_source_count=101)
    assert not hasattr(context, "tenant_id")


def test_api_mounts_initialized_local_embedding_cache() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
    api = compose["services"]["api"]
    assert "embedding_cache:/var/cache/fastembed" in api["volumes"]
    assert (
        api["depends_on"]["embedding-cache-init"]["condition"]
        == "service_completed_successfully"
    )
