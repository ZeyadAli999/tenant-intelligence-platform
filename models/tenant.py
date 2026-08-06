"""Tenant model and tenant-code normalization."""

from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EntityStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


def normalize_tenant_code(value: str) -> str:
    """Create the canonical tenant code used for login and uniqueness."""
    return value.strip().casefold()


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tenants_code"),
        CheckConstraint("status IN ('active', 'inactive')", name="status_valid"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(code) > 0", name="code_not_blank"),
        CheckConstraint("code = lower(trim(code))", name="code_normalized"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=EntityStatus.ACTIVE.value,
        server_default=EntityStatus.ACTIVE.value,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    @validates("code")
    def validate_code(self, _: str, value: str) -> str:
        return normalize_tenant_code(value)
