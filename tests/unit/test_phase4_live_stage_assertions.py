"""Tests that prevent Phase 4 smoke stages from reverting to placeholder success."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from scripts import phase4_live_stages as stages


def base_state() -> dict[str, object]:
    return {
        "admin_access_token": "admin-token",
        "normal_user_access_token": "normal-token",
        "second_tenant_access_token": "second-token",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "knowledge_base_id": "00000000-0000-0000-0000-000000000002",
        "file_ids": ["00000000-0000-0000-0000-000000000003"],
        "conversation_id": "00000000-0000-0000-0000-000000000004",
        "message_id": "00000000-0000-0000-0000-000000000005",
        "connection_id": "00000000-0000-0000-0000-000000000006",
    }


def test_embedding_stage_executes_vector_dimension_inspection(
    tmp_path, monkeypatch
) -> None:
    calls = []

    def inspect(action, *arguments):
        calls.append((action, arguments))
        return {
            "file_count": 1,
            "active_chunk_count": 2,
            "all_files_ready": True,
            "dimensions_ok": True,
            "active_generations_only": True,
        }

    monkeypatch.setattr(stages, "safe_inspect", inspect)
    stages.verify_embeddings(tmp_path, base_state(), "document")
    assert calls and calls[0][0] == "embeddings" and "--file-id" in calls[0][1]


class StreamResponse:
    status_code = 200
    headers: ClassVar[dict[str, str]] = {"content-type": "text/event-stream"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def iter_lines(self):
        payloads = [
            ("started", {"message_id": "stream-id"}),
            ("answer_delta", {"text": "safe "}),
            ("answer_delta", {"text": "answer"}),
            ("completed", {"message_id": "stream-id", "answer": "safe answer"}),
        ]
        for name, data in payloads:
            yield f"event: {name}"
            yield f"data: {json.dumps(data)}"
            yield ""


def test_sse_stage_calls_stream_and_reconstructs_persisted_answer(
    tmp_path, monkeypatch
) -> None:
    streamed = []
    monkeypatch.setattr(
        stages.httpx,
        "stream",
        lambda *a, **k: streamed.append((a, k)) or StreamResponse(),
    )

    def request(_state, _method, path, **_kwargs):
        if path.startswith("/conversations/"):
            return {"messages": [{"id": "stream-id", "content": "safe answer"}]}
        return {"items": [{"type": "document"}]}

    monkeypatch.setattr(stages, "request", request)
    state = base_state()
    stages.verify_sse(tmp_path, state, "document")
    assert streamed and state["sse_reconstruction_success"] is True


def test_malicious_document_stage_uploads_and_questions_as_normal_user(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "fixtures").mkdir()
    uploads = []
    requests = []
    monkeypatch.setattr(
        stages,
        "_upload_wait_one",
        lambda _state, path: uploads.append(path) or {"id": "malicious-id"},
    )

    def request(_state, method, path, **kwargs):
        requests.append((method, path, kwargs.get("token"), kwargs.get("json")))
        return {
            "sql": None,
            "sources_used": ["documents"],
            "answer": "Written approval is required.",
            "citations": [{"type": "document", "file_id": "malicious-id"}],
        }

    monkeypatch.setattr(stages, "request", request)
    stages.verify_inert_document(tmp_path, base_state(), "document")
    assert (
        uploads
        and requests[0][2] == "normal-token"
        and "approval" in requests[0][3]["message"].lower()
    )


def test_tenant_isolation_uses_second_tenant_token_for_every_denial(
    monkeypatch,
) -> None:
    tokens = []
    monkeypatch.setattr(
        stages,
        "request",
        lambda *_a, **kw: tokens.append(kw["token"]) or {"_status_code": 404},
    )
    stages.verify_tenant_isolation(Path(), base_state(), "document")
    assert len(tokens) == 5 and set(tokens) == {"second-token"}


def test_attack_stage_sends_every_attack_and_source_stage_compares_queries(
    tmp_path, monkeypatch
) -> None:
    attacks = []

    class Response:
        status_code = 400

    monkeypatch.setattr(
        stages.httpx,
        "post",
        lambda *a, **kw: attacks.append(kw["json"]["message"]) or Response(),
    )
    state = base_state()
    stages.verify_attack_rejection(tmp_path, state, "hybrid")
    assert len(attacks) == 6 and any("pg_catalog" in item for item in attacks)
    facts = {
        "row_count": 3,
        "table_exists": True,
        "columns": ["id"],
        "business_tables": ["customers"],
    }
    state["source_facts_before"] = facts
    calls = []
    monkeypatch.setattr(
        stages, "customer_source_facts", lambda: calls.append(True) or facts
    )
    stages.verify_source_unchanged(tmp_path, state, "hybrid")
    assert calls and state["source_integrity_success"] is True


def test_hybrid_stage_requires_both_citations_execution_and_normal_token(
    tmp_path, monkeypatch
) -> None:
    tokens = []

    def request(_state, _method, _path, **kwargs):
        tokens.append(kwargs["token"])
        return {
            "intent": "hybrid",
            "sources_used": ["database", "documents"],
            "answer": "safe",
            "sql": {"normalized_sql": "SELECT 1"},
            "message_id": "message",
            "citations": [{"type": "database"}, {"type": "document"}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "provider_latency_ms": 20,
            },
        }

    monkeypatch.setattr(stages, "request", request)
    monkeypatch.setattr(
        stages,
        "safe_inspect",
        lambda *_a: {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "query_execution": True,
            "validation_status": "accepted",
            "execution_status": "succeeded",
            "row_filter_applied": True,
            "masked_preview": True,
            "raw_tax_identifier_absent": True,
            "citation_types": ["database", "document"],
        },
    )
    stages.verify_hybrid_chat(tmp_path, base_state(), "hybrid")
    assert tokens == ["normal-token"]


def test_required_stages_are_dedicated_and_no_generic_checkpoint_remains() -> None:
    required = (
        "verify_embeddings",
        "verify_sse",
        "verify_inert_document",
        "verify_tenant_isolation",
        "verify_safe_query_and_citations",
        "verify_attack_rejection",
        "verify_source_unchanged",
    )
    assert not hasattr(stages, "generic_stage")
    assert all(callable(getattr(stages, name)) for name in required)
