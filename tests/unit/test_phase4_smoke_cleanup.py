"""Cleanup safety, idempotency, and sanitized stage-result regressions."""

from __future__ import annotations

from types import SimpleNamespace

from scripts import phase4_live_stages as live
from scripts.phase4_safe_inspect import SMOKE_CODE, validate_codes


def test_only_exact_smoke_tenant_codes_are_accepted() -> None:
    assert SMOKE_CODE.fullmatch("p4-012345abcdef")
    assert SMOKE_CODE.fullmatch("p4-other-012345abcdef")
    for unsafe in ("demo", "p4-prod", "p4-012345abcdeg", "p4-012345abcdef-extra"):
        try:
            validate_codes([unsafe])
        except ValueError as exc:
            assert str(exc) == "INVALID_SMOKE_TENANT_SELECTOR"
        else:
            raise AssertionError("ordinary tenant selector accepted")


def test_cleanup_attempts_every_step_and_preserves_first_category(
    monkeypatch, tmp_path
) -> None:
    calls: list[str] = []

    def inspect(action, *args):
        calls.append(action)
        if action == "remove_objects":
            raise RuntimeError("private object detail")
        if action == "cleanup_tenants":
            return {"remaining_tenants": 0}
        return {"counts": {"tenants": 0}, "total": 0}

    def request(*args, **kwargs):
        calls.append(str(args[2]))
        return {"_status_code": 404}

    monkeypatch.setattr(live, "safe_inspect", inspect)
    monkeypatch.setattr(live, "request", request)
    monkeypatch.setattr(
        live.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    state = {
        "tenant_code": "p4-012345abcdef",
        "second_tenant_code": "p4-other-012345abcdef",
        "knowledge_base_id": "kb",
        "connection_id": "connection",
        "normal_user_access_token": "token",
        "admin_access_token": "token",
        "source_facts_before": {},
    }
    result = live.cleanup(tmp_path, state)
    assert result["status"] == "failed"
    assert result["failure_category"] == "MINIO_CLEANUP_FAILED"
    assert calls[0] == "remove_objects"
    assert "cleanup_tenants" in calls and "remaining" in calls


def test_cleanup_404_and_absent_optional_resources_are_idempotent(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        live,
        "safe_inspect",
        lambda action, *args: (
            {"objects_remaining": 0}
            if action == "remove_objects"
            else {"remaining_tenants": 0}
            if action == "cleanup_tenants"
            else {"counts": {"tenants": 0}, "total": 0}
        ),
    )
    monkeypatch.setattr(live, "request", lambda *args, **kwargs: {"_status_code": 404})
    state = {
        "tenant_code": "p4-012345abcdef",
        "second_tenant_code": "p4-other-012345abcdef",
    }
    result = live.cleanup(tmp_path, state)
    assert result["status"] == "passed"
    assert result["remaining_resources"] == {"tenants": 0}


def test_child_failure_category_never_contains_raw_exception() -> None:
    category = live.safe_failure_category("verify_sse", RuntimeError("password=secret"))
    assert category == "SSE_CONTRACT_FAILED"
    assert "secret" not in category
