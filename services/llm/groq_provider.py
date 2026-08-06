"""Groq-only asynchronous strict structured-output provider."""

import asyncio
import json
from copy import deepcopy
from time import perf_counter
from typing import TypeVar

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    InternalServerError,
    RateLimitError,
)
from pydantic import ValidationError

from app.config import Settings
from services.llm.base import LLMProvider
from services.llm.errors import (
    LLMIncompleteError,
    LLMOutputError,
    LLMRefusalError,
    LLMTimeoutError,
)
from services.llm.schemas import (
    DocumentGroundedAnswer,
    DocumentQueryPlan,
    GroundedAnswer,
    HybridGroundedAnswer,
    ProviderResult,
    ProviderUsage,
    RequestClassification,
    SourceSelectionContext,
    SQLProposal,
    StructuredModel,
)

T = TypeVar("T", bound=StructuredModel)
TRANSIENT_ERRORS = (APIConnectionError, InternalServerError, RateLimitError)


class GroqProvider(LLMProvider):
    """Use Groq Chat Completions; authorization remains entirely backend-owned."""

    provider_name = "groq"

    def __init__(self, settings: Settings, client: AsyncGroq | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncGroq(
            api_key=settings.groq_api_key.get_secret_value(),
            timeout=settings.groq_timeout_seconds,
            max_retries=0,
        )

    async def _request(
        self, schema: type[T], schema_name: str, instructions: str, content: str
    ) -> ProviderResult[T]:
        started = perf_counter()
        for attempt in range(self.settings.groq_max_retries + 1):
            retry_delay = min(0.1 * (2**attempt), 0.5)
            try:
                response = await self.client.chat.completions.create(
                    model=self.settings.groq_model,
                    messages=(
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": content},
                    ),
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": strict_json_schema(schema),
                        },
                    },
                    reasoning_format="hidden",
                    temperature=0,
                    max_completion_tokens=self.settings.groq_max_output_tokens,
                    store=False,
                )
                if not response.choices:
                    raise LLMIncompleteError("Provider response was incomplete")
                choice = response.choices[0]
                message = choice.message
                if getattr(message, "refusal", None):
                    raise LLMRefusalError("Provider declined the request")
                if choice.finish_reason not in ("stop", None):
                    raise LLMIncompleteError("Provider response was incomplete")
                if not isinstance(message.content, str):
                    raise LLMOutputError("Provider returned invalid structured output")
                try:
                    parsed = schema.model_validate(json.loads(message.content))
                except (json.JSONDecodeError, ValidationError) as exc:
                    raise LLMOutputError(
                        "Provider returned invalid structured output"
                    ) from exc
                usage = response.usage
                return ProviderResult(
                    parsed,
                    self.settings.groq_model,
                    ProviderUsage(
                        getattr(usage, "prompt_tokens", None),
                        getattr(usage, "completion_tokens", None),
                        int((perf_counter() - started) * 1000),
                    ),
                    provider=self.provider_name,
                )
            except APITimeoutError as exc:
                if attempt >= self.settings.groq_max_retries:
                    raise LLMTimeoutError("Provider request timed out") from exc
            except TRANSIENT_ERRORS as exc:
                if attempt >= self.settings.groq_max_retries:
                    raise LLMOutputError("Provider request failed") from exc
                retry_delay = _retry_after_seconds(exc, retry_delay)
            except APIStatusError as exc:
                # Authentication, model, and invalid-request failures are terminal.
                raise LLMOutputError("Provider request failed") from exc
            if attempt < self.settings.groq_max_retries:
                await asyncio.sleep(retry_delay)
        raise LLMOutputError("Provider request failed")

    async def classify(
        self,
        question: str,
        history: tuple[str, ...],
        source_selection: SourceSelectionContext,
    ) -> ProviderResult[RequestClassification]:
        from agents.prompts.classifier_v1 import CLASSIFIER_INSTRUCTIONS

        return await self._request(
            RequestClassification,
            "request_classification",
            CLASSIFIER_INSTRUCTIONS,
            "SOURCE_SELECTION="
            f"{source_selection.model_dump_json()}\n"
            f"HISTORY_DATA={list(history)!r}\nQUESTION_DATA={question!r}",
        )

    async def propose_sql(
        self,
        question: str,
        schema: str,
        source_selection: SourceSelectionContext | None = None,
    ) -> ProviderResult[SQLProposal]:
        from agents.prompts.sql_generator_v1 import SQL_GENERATOR_INSTRUCTIONS

        return await self._request(
            SQLProposal,
            "sql_proposal",
            SQL_GENERATOR_INSTRUCTIONS,
            "SOURCE_SELECTION="
            f"{(source_selection or SourceSelectionContext()).model_dump_json()}\n"
            f"UNTRUSTED_SCHEMA_DATA={schema}\nQUESTION_DATA={question!r}",
        )

    async def repair_sql(
        self,
        question: str,
        schema: str,
        previous_sql: str,
        error_codes: tuple[str, ...],
    ) -> ProviderResult[SQLProposal]:
        from agents.prompts.sql_generator_v1 import SQL_REPAIR_INSTRUCTIONS

        return await self._request(
            SQLProposal,
            "sql_repair",
            SQL_REPAIR_INSTRUCTIONS,
            f"UNTRUSTED_SCHEMA_DATA={schema}\nQUESTION_DATA={question!r}\nPREVIOUS_SQL_DATA={previous_sql!r}\nSAFE_ERROR_CODES={error_codes!r}",
        )

    async def generate_answer(
        self, question: str, result: dict[str, object]
    ) -> ProviderResult[GroundedAnswer]:
        from agents.prompts.answer_generator_v1 import ANSWER_INSTRUCTIONS

        return await self._request(
            GroundedAnswer,
            "grounded_answer",
            ANSWER_INSTRUCTIONS,
            f"QUESTION_DATA={question!r}\nAPPROVED_MASKED_RESULT_DATA={result!r}",
        )

    async def rewrite_document_query(
        self, question: str, history: tuple[str, ...]
    ) -> ProviderResult[DocumentQueryPlan]:
        from agents.prompts.document_v1 import DOCUMENT_REWRITE_INSTRUCTIONS

        return await self._request(
            DocumentQueryPlan,
            "document_query_rewrite",
            DOCUMENT_REWRITE_INSTRUCTIONS,
            f"HISTORY_DATA={list(history)!r}\nQUESTION_DATA={question!r}",
        )

    async def generate_document_answer(
        self, question: str, evidence: dict[str, object]
    ) -> ProviderResult[DocumentGroundedAnswer]:
        from agents.prompts.document_v1 import DOCUMENT_ANSWER_INSTRUCTIONS

        return await self._request(
            DocumentGroundedAnswer,
            "document_grounded_answer",
            DOCUMENT_ANSWER_INSTRUCTIONS,
            f"QUESTION_DATA={question!r}\nUNTRUSTED_APPROVED_EVIDENCE_DATA={evidence!r}",
        )

    async def generate_hybrid_answer(
        self, question: str, evidence: dict[str, object]
    ) -> ProviderResult[HybridGroundedAnswer]:
        from agents.prompts.document_v1 import HYBRID_ANSWER_INSTRUCTIONS

        return await self._request(
            HybridGroundedAnswer,
            "hybrid_grounded_answer",
            HYBRID_ANSWER_INSTRUCTIONS,
            f"QUESTION_DATA={question!r}\nUNTRUSTED_APPROVED_EVIDENCE_DATA={evidence!r}",
        )


def strict_json_schema(model: type[StructuredModel]) -> dict[str, object]:
    """Convert Pydantic schema to Groq's closed, all-fields-required subset."""

    schema = deepcopy(model.model_json_schema())

    def close(node: object) -> None:
        if isinstance(node, dict):
            # Groq strict schemas do not accept Pydantic's annotation-only defaults.
            node.pop("default", None)
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                close(value)
        elif isinstance(node, list):
            for value in node:
                close(value)

    close(schema)
    return schema


def _retry_after_seconds(error: Exception, fallback: float) -> float:
    response = getattr(error, "response", None)
    header = response.headers.get("Retry-After") if response is not None else None
    try:
        return max(0.0, min(float(header), 30.0)) if header is not None else fallback
    except (TypeError, ValueError):
        return fallback
