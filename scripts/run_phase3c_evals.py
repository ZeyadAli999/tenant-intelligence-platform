"""Backward-compatible entry point for the Phase 3C evaluation harness."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_text_to_sql import evaluate


async def main() -> int:
    report, status = await evaluate(live=False)
    import json

    print(json.dumps(report, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
