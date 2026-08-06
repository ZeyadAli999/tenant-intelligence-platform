"""Dramatiq document retry taxonomy tests without Redis or external models."""

from uuid import uuid4

import pytest

import workers.document_tasks as tasks


def test_retryable_error_is_sanitized() -> None:
    error = tasks.RetryableDocumentError("STORAGE_TEMPORARILY_UNAVAILABLE")
    assert str(error) == "STORAGE_TEMPORARILY_UNAVAILABLE"


def test_actor_reraises_before_exhaustion(monkeypatch) -> None:
    async def fail(*_):
        raise tasks.RetryableDocumentError("INFRASTRUCTURE_TEMPORARILY_UNAVAILABLE")

    monkeypatch.setattr(tasks, "_process", fail)
    monkeypatch.setattr(tasks, "_current_retry_count", lambda: 1)
    with pytest.raises(tasks.RetryableDocumentError):
        tasks.process_document.fn(str(uuid4()), str(uuid4()), 1)


def test_actor_persists_safe_failure_at_final_exhaustion(monkeypatch) -> None:
    calls: list[str] = []

    async def fail(*_):
        raise tasks.RetryableDocumentError("DOCUMENT_PROCESSING_FAILED")

    async def mark(*args):
        calls.append(args[-1])

    monkeypatch.setattr(tasks, "_process", fail)
    monkeypatch.setattr(tasks, "_mark_failed", mark)
    monkeypatch.setattr(tasks, "_current_retry_count", lambda: tasks.MAX_RETRIES)
    tasks.process_document.fn(str(uuid4()), str(uuid4()), 1)
    assert calls == ["DOCUMENT_PROCESSING_FAILED"]
