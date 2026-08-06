"""Tenant-owned user model."""

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from database.base import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from models.tenant import EntityStatus


def normalize_email(value: str) -> str:
    """Create the canonical email used for tenant-scoped identity matching."""
    return value.strip().casefold()


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        UniqueConstraint("id", "tenant_id", name="uq_users_id_tenant"),
        CheckConstraint("status IN ('active', 'inactive')", name="status_valid"),
        CheckConstraint("length(email) > 0", name="email_not_blank"),
        CheckConstraint("email = lower(trim(email))", name="email_normalized"),
        Index("idx_users_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=EntityStatus.ACTIVE.value,
        server_default=EntityStatus.ACTIVE.value,
    )
    is_tenant_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    @validates("email")
    def validate_email(self, _: str, value: str) -> str:
        return normalize_email(value)
