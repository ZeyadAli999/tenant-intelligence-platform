"""Safe, distinct diagnostics for the real Document Chat smoke contract."""

from __future__ import annotations

import json

import pytest

from scripts import phase4_live_stages as live
from scripts import phase4_smoke

SAFE_DOCUMENT_KEYS = {
    "actual_intent",
    "sources_used",
    "sql_present",
    "answer_present",
    "total_citation_count",
    "document_citation_count",
    "citation_scope_valid",
    "message_id_present",
    "usage_present",
}


def response() -> dict[str, object]:
    return {
        "message_id": "secret-message-id",
        "intent": "document",
        "sources_used": ["documents"],
        "sql": None,
        "answer": "secret answer text",
        "citations": [
            {
                "type": "document",
                "file_id": "allowed-file-id",
                "chunk_id": "secret-chunk-id",
            }
        ],
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "provider_latency_ms": 4,
        },
    }


@pytest.mark.parametrize(
    ("mutation", "category"),
    [
        ({"intent": "general"}, "DOCUMENT_INTENT_MISMATCH"),
        ({"sources_used": []}, "DOCUMENT_SOURCES_MISMATCH"),
        ({"sql": {"normalized_sql": "SELECT 1"}}, "DOCUMENT_SQL_PRESENT"),
        ({"answer": ""}, "DOCUMENT_ANSWER_EMPTY"),
        ({"citations": []}, "DOCUMENT_CITATIONS_MISSING"),
        (
            {
                "citations": [
                    {"type": "document", "file_id": "outside", "chunk_id": "hidden"}
                ]
            },
            "DOCUMENT_CITATION_SCOPE_FAILED",
        ),
        ({"usage": None}, "DOCUMENT_USAGE_MISSING"),
        ({"message_id": None}, "DOCUMENT_MESSAGE_ID_MISSING"),
    ],
)
def test_document_contract_conditions_have_distinct_safe_categories(
    mutation, category, monkeypatch, tmp_path
) -> None:
    payload = response()
    payload.update(mutation)
    monkeypatch.setattr(live, "request", lambda *args, **kwargs: payload)
    state = {
        "normal_user_access_token": "token",
        "conversation_id": "conversation",
        "knowledge_base_id": "kb",
        "file_ids": ["allowed-file-id"],
        "tenant_id": "tenant",
    }
    with pytest.raises(live.StageContractFailure) as raised:
        live.verify_document_chat(tmp_path, state, "document")
    assert raised.value.category == category
    assert set(raised.value.details) == SAFE_DOCUMENT_KEYS
    serialized = json.dumps(raised.value.details)
    for prohibited in (
        "secret answer text",
        "secret-message-id",
        "allowed-file-id",
        "secret-chunk-id",
    ):
        assert prohibited not in serialized


@pytest.mark.parametrize(
    ("persisted", "mismatched_key"),
    [
        ({"provider": "other", "model": "openai/gpt-oss-120b"}, "actual_provider"),
        ({"provider": "groq", "model": "other-model"}, "actual_model"),
    ],
)
def test_provider_metadata_mismatches_have_allowlisted_details(
    persisted, mismatched_key, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(live, "request", lambda *args, **kwargs: response())
    monkeypatch.setattr(live, "safe_inspect", lambda *args, **kwargs: persisted)
    state = {
        "normal_user_access_token": "token",
        "conversation_id": "conversation",
        "knowledge_base_id": "kb",
        "file_ids": ["allowed-file-id"],
        "tenant_id": "tenant",
    }
    with pytest.raises(live.StageContractFailure) as raised:
        live.verify_document_chat(tmp_path, state, "document")
    assert raised.value.category == "DOCUMENT_PROVIDER_METADATA_FAILED"
    assert set(raised.value.details) == {
        "actual_provider",
        "actual_model",
        "expected_provider",
        "expected_model",
    }
    assert raised.value.details[mismatched_key] == persisted[mismatched_key[7:]]


def test_parent_detail_filter_rejects_answers_ids_and_unknown_fields() -> None:
    details = phase4_smoke._safe_stage_details(
        {
            "actual_intent": "general",
            "answer": "secret answer",
            "message_id": "secret id",
            "file_id": "secret file",
            "unknown": "secret",
        }
    )
    assert details == {"actual_intent": "general"}
