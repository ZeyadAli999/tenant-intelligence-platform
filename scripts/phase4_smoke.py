"""Shared, testable orchestration for the opt-in Phase 4 real smoke flows."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

DIAGNOSTIC_PATH = (
    Path(__file__).resolve().parents[1] / "outputs" / "phase4-smoke-last-result.json"
)

DOCUMENT_STAGES = (
    "verify_infrastructure",
    "create_identities",
    "authenticate",
    "create_knowledge_base",
    "generate_fixtures",
    "upload_and_wait",
    "verify_embeddings",
    "create_conversation",
    "verify_document_chat",
    "verify_citations",
    "verify_sse",
    "verify_inert_document",
    "verify_tenant_isolation",
)

HYBRID_STAGES = (
    "verify_infrastructure",
    "create_identities",
    "authenticate",
    "create_customer_database",
    "configure_connection",
    "configure_permissions",
    "create_knowledge_base",
    "upload_and_wait",
    "create_conversation",
    "verify_hybrid_chat",
    "verify_safe_query_and_citations",
    "verify_sse",
    "verify_attack_rejection",
    "verify_source_unchanged",
)


@dataclass
class SmokeSummary:
    provider: str = "groq"
    model: str = "openai/gpt-oss-120b"
    metrics: dict[str, int | bool | str] = field(default_factory=dict)


class SmokeFlow(ABC):
    """A complete smoke flow; stages are explicit so tests cannot hide omissions."""

    summary: SmokeSummary
    mode: str
    completed_stages: list[str]

    @abstractmethod
    def run_stage(self, name: str) -> None: ...

    @abstractmethod
    def cleanup(self) -> None: ...

    def close(self) -> None:
        """Release temporary local state after diagnostics have been written."""


class SmokeStageFailure(Exception):
    def __init__(
        self, stage: str, category: str, details: dict[str, object] | None = None
    ) -> None:
        self.stage = stage
        self.category = category
        self.details = details or {}
        super().__init__(category)


class SmokeCleanupFailure(Exception):
    def __init__(
        self,
        category: str,
        *,
        step_statuses: dict[str, str] | None = None,
        remaining: dict[str, int | bool] | None = None,
    ) -> None:
        self.category = category
        self.step_statuses = step_statuses or {}
        self.remaining = remaining or {}
        super().__init__(category)


def authorized() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return (
        os.getenv("RUN_REAL_GROQ_VERIFICATION") == "1"
        and len(key) >= 20
        and "replace-with" not in key.lower()
    )


def run_flow(flow: SmokeFlow, stages: tuple[str, ...]) -> int:
    failed_stage: str | None = None
    primary_category: str | None = None
    primary_details: dict[str, object] = {}
    cleanup_category: str | None = None
    cleanup_status = "passed"
    cleanup_steps: dict[str, str] = {}
    remaining: dict[str, int | bool] = {}
    try:
        for stage in stages:
            flow.run_stage(stage)
    except SmokeStageFailure as exc:
        failed_stage = exc.stage
        primary_category = exc.category
        primary_details = _safe_stage_details(exc.details)
    except Exception:  # noqa: BLE001 - fail closed without raw exception details
        failed_stage = (
            stages[len(flow.completed_stages)]
            if len(flow.completed_stages) < len(stages)
            else None
        )
        primary_category = "SMOKE_STAGE_FAILED"
    try:
        flow.cleanup()
    except SmokeCleanupFailure as exc:
        cleanup_status = "failed"
        cleanup_category = exc.category
        cleanup_steps = exc.step_statuses
        remaining = exc.remaining
    except Exception:  # noqa: BLE001 - never leak cleanup implementation details
        cleanup_status = "failed"
        cleanup_category = "CLEANUP_FAILED"
    status = "failed" if primary_category or cleanup_category else "passed"
    payload: dict[str, object] = {
        "status": status,
        "failed_stage": failed_stage,
        "primary_failure_category": primary_category,
        "primary_failure_details": primary_details,
        "cleanup_status": cleanup_status,
        "cleanup_failure_category": cleanup_category,
    }
    if status == "passed":
        payload.update(
            provider=flow.summary.provider,
            model=flow.summary.model,
            **flow.summary.metrics,
        )
    else:
        _write_diagnostic(
            mode=flow.mode,
            completed_stages=flow.completed_stages,
            failed_stage=failed_stage,
            primary_category=primary_category,
            primary_details=primary_details,
            cleanup_category=cleanup_category,
            cleanup_steps=cleanup_steps,
            remaining=remaining,
        )
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    flow.close()
    return 1 if status == "failed" else 0


def _write_diagnostic(
    *,
    mode: str,
    completed_stages: list[str],
    failed_stage: str | None,
    primary_category: str | None,
    primary_details: dict[str, object],
    cleanup_category: str | None,
    cleanup_steps: dict[str, str],
    remaining: dict[str, int | bool],
) -> None:
    output = DIAGNOSTIC_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "mode": mode,
                "completed_stages": completed_stages,
                "failed_stage": failed_stage,
                "primary_failure_category": primary_category,
                "primary_failure_details": primary_details,
                "cleanup_failure_category": cleanup_category,
                "cleanup_steps": cleanup_steps,
                "remaining_resources": remaining,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


class CommandBackedFlow(SmokeFlow):
    """Concrete disposable flow driven by a checked-in stage implementation.

    Each stage is executed in a fresh process with secrets inherited through the
    environment (never command arguments). The implementation module performs
    API calls, fixture generation, assertions, and resource registration in one
    persisted temporary state directory.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.summary = SmokeSummary()
        self.completed_stages: list[str] = []
        self._state = tempfile.TemporaryDirectory(prefix=f"phase4-{mode}-")
        self._root = Path(self._state.name)

    def run_stage(self, name: str) -> None:
        completed = subprocess.run(
            [
                os.sys.executable,
                "-m",
                "scripts.phase4_live_stages",
                self.mode,
                name,
                str(self._root),
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise SmokeStageFailure(name, "STAGE_RESULT_INVALID") from exc
        if completed.returncode != 0 or result.get("status") != "passed":
            raise SmokeStageFailure(
                name,
                str(result.get("failure_category") or "SMOKE_STAGE_FAILED"),
                details=_safe_stage_details(result.get("details")),
            )
        self.completed_stages.append(name)
        self.summary.metrics.update(result.get("metrics", {}))

    def cleanup(self) -> None:
        completed = subprocess.run(
            [
                os.sys.executable,
                "-m",
                "scripts.phase4_live_stages",
                self.mode,
                "cleanup",
                str(self._root),
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise SmokeCleanupFailure("CLEANUP_RESULT_INVALID") from exc
        if completed.returncode or result.get("status") != "passed":
            raise SmokeCleanupFailure(
                str(result.get("failure_category") or "CLEANUP_FAILED"),
                step_statuses=dict(result.get("cleanup_steps", {})),
                remaining=dict(result.get("remaining_resources", {})),
            )

    def close(self) -> None:
        self._state.cleanup()


FlowFactory = Callable[[], SmokeFlow]


SAFE_STAGE_DETAIL_KEYS = {
    "actual_intent",
    "sources_used",
    "sql_present",
    "answer_present",
    "total_citation_count",
    "document_citation_count",
    "citation_scope_valid",
    "message_id_present",
    "usage_present",
    "actual_provider",
    "actual_model",
    "expected_provider",
    "expected_model",
}


def _safe_stage_details(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item for key, item in value.items() if key in SAFE_STAGE_DETAIL_KEYS
    }
