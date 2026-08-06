"""Hashed refresh-token session records with rotation-family tracking."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.mixins import UUIDPrimaryKeyMixin


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            name="fk_refresh_tokens_user_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("jti", name="uq_refresh_tokens_jti"),
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_tenant_id", "tenant_id"),
        Index("idx_refresh_tokens_family_id", "family_id"),
        Index("idx_refresh_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    jti: Mapped[UUID] = mapped_column(nullable=False, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(nullable=False, default=uuid4)
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_jti: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.jti", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
