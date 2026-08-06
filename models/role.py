"""Tenant roles and tenant-consistent user-role assignments."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from database.base import Base
from models.mixins import UUIDPrimaryKeyMixin


def normalize_role_name(value: str) -> str:
    """Create the canonical tenant-scoped role name."""
    return value.strip().casefold()


class Role(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
        UniqueConstraint("id", "tenant_id", name="uq_roles_id_tenant"),
        CheckConstraint("length(name) > 0", name="name_not_blank"),
        CheckConstraint("name = lower(trim(name))", name="name_normalized"),
        Index("idx_roles_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    @validates("name")
    def validate_name(self, _: str, value: str) -> str:
        return normalize_role_name(value)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_user_roles_user_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["roles.id", "roles.tenant_id"],
            name="fk_user_roles_role_tenant",
            ondelete="CASCADE",
        ),
        Index("idx_user_roles_tenant_id", "tenant_id"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    role_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
