"""Opt-in complete real Groq hybrid smoke flow."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase4_smoke import (
    HYBRID_STAGES,
    CommandBackedFlow,
    FlowFactory,
    authorized,
    run_flow,
)


def main(flow_factory: FlowFactory | None = None) -> int:
    if not authorized():
        print("Real Groq hybrid smoke check not executed")
        return 0
    factory = flow_factory or (lambda: CommandBackedFlow("hybrid"))
    return run_flow(factory(), HYBRID_STAGES)


if __name__ == "__main__":
    raise SystemExit(main())
