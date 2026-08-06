"""Establish the Phase 1 migration baseline.

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

revision: str = "20260803_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no domain tables during the infrastructure-only phase."""


def downgrade() -> None:
    """Remove no domain tables during the infrastructure-only phase."""
