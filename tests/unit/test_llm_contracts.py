"""Strict Groq structured-output and provider-boundary tests."""

import json
from types import SimpleNamespace

import httpx
import pytest
from groq import APITimeoutError, AuthenticationError, RateLimitError
from pydantic import ValidationError

from app.config import Settings
from services.llm.errors import LLMIncompleteError, LLMOutputError, LLMRefusalError
from services.llm.factory import build_llm_provider
from services.llm.groq_provider import GroqProvider
from services.llm.schemas import (
    RequestClassification,
    SourceSelectionContext,
    SQLProposal,
)


class Completions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, object] | None = None

    async def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return self.response


class SequentialCompletions(Completions):
    def __init__(self, values: list[object]) -> None:
        super().__init__(values[-1])
        self.values = values
        self.calls = 0

    async def create(self, **kwargs: object) -> object:
        self.calls += 1
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def response(content: str, *, finish: str = "stop", refusal: str | None = None):
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
    )


def provider(value: object) -> tuple[GroqProvider, Completions]:
    completions = Completions(value)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return GroqProvider(Settings(), client=client), completions


def test_structured_contracts_reject_extra_fields_and_invalid_pairs() -> None:
    with pytest.raises(ValidationError):
        RequestClassification(
            intent="database", confidence=1, short_reason="ok", injected=True
        )
    with pytest.raises(ValidationError):
        SQLProposal(action="generate_sql", sql=None, short_description="bad")


@pytest.mark.asyncio
async def test_groq_provider_sends_strict_schema_and_disables_storage() -> None:
    payload = {
        "intent": "general",
        "confidence": 1,
        "clarification_question": None,
        "short_reason": "general",
    }
    subject, completions = provider(response(json.dumps(payload)))
    result = await subject.classify("hello", (), SourceSelectionContext())

    assert result.value == RequestClassification(**payload)
    assert result.provider == "groq"
    assert completions.kwargs is not None
    assert completions.kwargs["store"] is False
    assert completions.kwargs["reasoning_format"] == "hidden"
    assert completions.kwargs["model"] == "openai/gpt-oss-120b"
    response_format = completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"  # type: ignore[index]
    json_schema = response_format["json_schema"]  # type: ignore[index]
    assert json_schema["strict"] is True
    assert json_schema["schema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_groq_classifier_receives_only_safe_source_selection_metadata() -> None:
    payload = {
        "intent": "document",
        "confidence": 1,
        "clarification_question": None,
        "short_reason": "selected documents",
    }
    subject, completions = provider(response(json.dumps(payload)))
    context = SourceSelectionContext(
        document_sources_selected=True, document_source_count=1
    )
    await subject.classify("safe question", (), context)
    assert completions.kwargs is not None
    user_content = completions.kwargs["messages"][1]["content"]  # type: ignore[index]
    assert "document_sources_selected" in user_content
    assert "document_source_count" in user_content
    for forbidden in (
        "tenant_id",
        "user_id",
        "knowledge_base_id",
        "connection_id",
        "schema",
        "credential",
        "object_key",
    ):
        assert forbidden not in user_content


@pytest.mark.asyncio
async def test_groq_provider_parses_sql_and_grounded_answer_contracts() -> None:
    sql_payload = {
        "action": "generate_sql",
        "sql": "SELECT id FROM business.customers",
        "clarification_question": None,
        "short_description": "approved customer identifiers",
        "proposed_tables": ["business.customers"],
        "proposed_columns": ["business.customers.id"],
    }
    sql_subject, _ = provider(response(json.dumps(sql_payload)))
    proposal = await sql_subject.propose_sql("List customers", "approved schema")
    assert proposal.value == SQLProposal(**sql_payload)

    answer_payload = {
        "answer": "The approved query returned two rows.",
        "warnings": [],
        "result_summary_type": "rows",
    }
    answer_subject, _ = provider(response(json.dumps(answer_payload)))
    answer = await answer_subject.generate_answer(
        "List customers", {"rows": [{"id": 1}, {"id": 2}]}
    )
    assert answer.value.answer == answer_payload["answer"]


@pytest.mark.asyncio
async def test_hybrid_sql_proposal_receives_only_safe_source_categories() -> None:
    payload = {
        "action": "generate_sql",
        "sql": "SELECT tax_identifier FROM business.customers",
        "clarification_question": None,
        "short_description": "approved database evidence",
        "proposed_tables": ["business.customers"],
        "proposed_columns": ["business.customers.tax_identifier"],
    }
    subject, completions = provider(response(json.dumps(payload)))
    await subject.propose_sql(
        "Use customer records and documents",
        "approved schema",
        SourceSelectionContext(
            database_sources_selected=True,
            document_sources_selected=True,
            database_source_count=1,
            document_source_count=1,
        ),
    )
    user_content = completions.kwargs["messages"][1]["content"]  # type: ignore[index]
    assert '"database_sources_selected":true' in user_content
    assert '"document_sources_selected":true' in user_content
    assert "knowledge_base_id" not in user_content
    assert "connection_id" not in user_content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "error_type"),
    [
        (response("{}", finish="length"), LLMIncompleteError),
        (response("not-json"), LLMOutputError),
        (response("{}", refusal="declined"), LLMRefusalError),
    ],
)
async def test_groq_provider_rejects_incomplete_malformed_and_refused_output(
    value: object, error_type: type[Exception]
) -> None:
    subject, _ = provider(value)
    with pytest.raises(error_type):
        await subject.classify("hello", (), SourceSelectionContext())


def test_normal_factory_constructs_groq_and_never_fake() -> None:
    settings = Settings()
    subject = build_llm_provider(settings)
    assert isinstance(subject, GroqProvider)
    assert "llm_provider" not in type(settings).model_fields


def test_provider_constructs_official_async_groq_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = object()
    captured: dict[str, object] = {}

    def client(**kwargs: object) -> object:
        captured.update(kwargs)
        return marker

    monkeypatch.setattr("services.llm.groq_provider.AsyncGroq", client)
    subject = GroqProvider(Settings())
    assert subject.client is marker
    assert "api_key" in captured and captured["max_retries"] == 0


@pytest.mark.asyncio
async def test_timeout_and_rate_limit_retries_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("services.llm.groq_provider.asyncio.sleep", lambda _: _noop())
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    rate_response = httpx.Response(429, request=request, headers={"Retry-After": "0"})
    payload = json.dumps(
        {
            "intent": "general",
            "confidence": 1,
            "clarification_question": None,
            "short_reason": "general",
        }
    )
    completions = SequentialCompletions(
        [
            APITimeoutError(request),
            RateLimitError("rate limited", response=rate_response, body=None),
            response(payload),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    subject = GroqProvider(Settings(groq_max_retries=2), client=client)
    result = await subject.classify("hello", (), SourceSelectionContext())
    assert result.value.intent == "general"
    assert completions.calls == 3


@pytest.mark.asyncio
async def test_rate_limit_retry_after_is_honored_with_safe_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("services.llm.groq_provider.asyncio.sleep", record)
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    rate_response = httpx.Response(429, request=request, headers={"Retry-After": "12"})
    payload = json.dumps(
        {
            "intent": "general",
            "confidence": 1,
            "clarification_question": None,
            "short_reason": "general",
        }
    )
    completions = SequentialCompletions(
        [
            RateLimitError("rate limited", response=rate_response, body=None),
            response(payload),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    subject = GroqProvider(Settings(groq_max_retries=1), client=client)
    await subject.classify("hello", (), SourceSelectionContext())
    assert delays == [12.0]


@pytest.mark.asyncio
async def test_invalid_credentials_are_not_retried_or_leaked() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    auth_response = httpx.Response(401, request=request)
    completions = SequentialCompletions(
        [
            AuthenticationError(
                "secret provider detail", response=auth_response, body=None
            )
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    subject = GroqProvider(Settings(groq_max_retries=3), client=client)
    with pytest.raises(LLMOutputError) as captured:
        await subject.classify("hello", (), SourceSelectionContext())
    assert completions.calls == 1
    assert "secret provider detail" not in str(captured.value)


async def _noop() -> None:
    return None
