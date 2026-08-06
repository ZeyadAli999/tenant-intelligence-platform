"""Sanitized Phase 3C offline or live PostgreSQL evaluation report."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from services.llm.fake_provider import FakeLLMProvider
from services.llm.groq_provider import GroqProvider
from services.llm.schemas import SourceSelectionContext


async def evaluate(
    *, live: bool = False, real_groq: bool = False
) -> tuple[dict[str, object], int]:
    cases = json.loads(
        (PROJECT_ROOT / "evals/phase3c_database_chat.json").read_text(encoding="utf-8")
    )
    provider = GroqProvider(Settings()) if real_groq else FakeLLMProvider()
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    for case in cases:
        started = perf_counter()
        classification = (
            await provider.classify(
                case["question"],
                (),
                SourceSelectionContext(
                    database_sources_selected=True, database_source_count=1
                ),
            )
        ).value
        latencies.append((perf_counter() - started) * 1000)
        proposal_valid: bool | None = None
        if classification.intent == "database":
            proposal = (
                await provider.propose_sql(
                    case["question"], "permission-filtered fixture schema"
                )
            ).value
            proposal_valid = proposal.action in {"generate_sql", "ask_clarification"}
        records.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "intent_correct": classification.intent == case["expected_intent"],
                "clarification_correct": (
                    bool(classification.clarification_question)
                    if case["kind"] == "clarification"
                    else None
                ),
                "structured_proposal_valid": proposal_valid,
                "expected_safe_sql_behavior": "reject"
                if case["kind"] == "malicious"
                else (
                    "execute"
                    if case["kind"] in {"legitimate", "masked", "row_filter"}
                    else "not_applicable"
                ),
                "validator_accepted": None,
                "validator_rejected": None,
                "execution_succeeded": None,
                "expected_result_correct": None,
                "row_filter_compliant": None,
                "masking_compliant": None,
                "failure_category": None,
            }
        )

    live_report: dict[str, object] = {
        "executed": False,
        "reason": "use --live with disposable PostgreSQL settings",
    }
    live_status = 0
    if live:
        required = (
            "TEST_DATABASE_URL",
            "CUSTOMER_TEST_HOST",
            "CUSTOMER_TEST_DATABASE",
            "CUSTOMER_TEST_USERNAME",
            "CUSTOMER_TEST_PASSWORD",
        )
        if not all(os.environ.get(name) for name in required):
            live_report = {
                "executed": False,
                "reason": "disposable PostgreSQL settings missing",
            }
            live_status = 2
        else:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/integration/test_safe_query_postgresql.py",
                "tests/integration/test_customer_postgresql.py",
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            passed = await process.wait() == 0
            live_report = {
                "executed": True,
                "passed": passed,
                "suite": "real SafeQueryService + disposable PostgreSQL",
                "per_case_dataset_scored": False,
                "scope": (
                    "integration security assertions only; no per-case metric is "
                    "inferred from the suite result"
                ),
            }
            live_status = 0 if passed else 1

    intent_accuracy = sum(bool(item["intent_correct"]) for item in records) / len(
        records
    )
    clarification = [item for item in records if item["kind"] == "clarification"]
    proposals = [
        item for item in records if item["structured_proposal_valid"] is not None
    ]
    report = {
        "evaluation_type": (
            "real Groq per-case model evaluation"
            if real_groq
            else "test-double per-case regression evaluation"
        ),
        "natural_language_model_quality_claimed": real_groq,
        "cases": records,
        "aggregates": {
            "case_count": len(records),
            "intent_accuracy": intent_accuracy,
            "clarification_accuracy": sum(
                bool(item["clarification_correct"]) for item in clarification
            )
            / len(clarification),
            "structured_proposal_validity": sum(
                bool(item["structured_proposal_valid"]) for item in proposals
            )
            / len(proposals),
            "average_classification_latency_ms": round(
                sum(latencies) / len(latencies), 3
            ),
        },
        "live_postgresql": live_report,
        "real_groq_model": {
            "executed": real_groq,
            "command": "python scripts/smoke_groq_phase3c.py",
        },
    }
    offline_status = (
        0
        if intent_accuracy == 1
        and all(bool(item["structured_proposal_valid"]) for item in proposals)
        else 1
    )
    return report, max(offline_status, live_status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-groq",
        action="store_true",
        help="Explicitly evaluate all cases with configured real Groq credentials",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run the real disposable PostgreSQL safety evaluation",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print sanitized aggregates without per-case records",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result, status = asyncio.run(
        evaluate(live=arguments.live, real_groq=arguments.real_groq)
    )
    output = (
        {
            "aggregates": result["aggregates"],
            "live_postgresql": result["live_postgresql"],
            "natural_language_model_quality_claimed": False,
        }
        if arguments.summary
        else result
    )
    print(json.dumps(output, sort_keys=True))
    raise SystemExit(status)
