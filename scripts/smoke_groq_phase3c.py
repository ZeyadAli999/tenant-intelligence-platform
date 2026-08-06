"""Explicit, sanitized, three-call real Groq smoke verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import sqlglot
from pydantic import ValidationError
from sqlglot import exp

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from services.llm.groq_provider import GroqProvider
from services.llm.schemas import SourceSelectionContext


async def run() -> None:
    if os.getenv("RUN_REAL_GROQ_VERIFICATION") != "1":
        print("Real Groq verification not executed")
        return
    try:
        settings = Settings()
    except ValidationError:
        print("Real Groq verification not executed")
        return

    provider = GroqProvider(settings)
    classification = await provider.classify(
        "How many customers are there?",
        (),
        SourceSelectionContext(database_sources_selected=True, database_source_count=1),
    )
    proposal = await provider.propose_sql(
        "How many customers are there?",
        "APPROVED_SCHEMA: business.customers(id: integer)",
    )
    answer = await provider.generate_answer(
        "How many customers are there?",
        {"columns": ["customer_count"], "rows": [{"customer_count": 2}]},
    )
    sql = proposal.value.sql or ""
    statements = sqlglot.parse(sql, read="postgres")
    if (
        proposal.value.action != "generate_sql"
        or len(statements) != 1
        or not isinstance(statements[0], exp.Select)
    ):
        raise RuntimeError("Groq smoke SQL did not satisfy the read-only contract")
    results = (classification, proposal, answer)
    print("status=passed")
    print("provider=groq")
    print(f"model={settings.groq_model}")
    print("successful_call_count=3")
    print(
        f"total_input_tokens={sum(item.usage.prompt_tokens or 0 for item in results)}"
    )
    print(
        "total_output_tokens="
        f"{sum(item.usage.completion_tokens or 0 for item in results)}"
    )
    print(f"total_latency_ms={sum(item.usage.latency_ms or 0 for item in results)}")
    print("structured_parsing_success=true")


if __name__ == "__main__":
    asyncio.run(run())
