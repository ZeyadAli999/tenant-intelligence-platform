"""Keep the deterministic evaluation corpus executable in CI."""

import json
from pathlib import Path

import pytest

from services.llm.fake_provider import FakeLLMProvider
from services.llm.schemas import SourceSelectionContext


@pytest.mark.asyncio
async def test_phase3c_eval_intent_corpus() -> None:
    cases = json.loads(
        Path("evals/phase3c_database_chat.json").read_text(encoding="utf-8")
    )
    provider = FakeLLMProvider()
    assert len(cases) >= 25
    for case in cases:
        result = await provider.classify(case["question"], (), SourceSelectionContext())
        assert result.value.intent == case["expected_intent"], case["id"]
