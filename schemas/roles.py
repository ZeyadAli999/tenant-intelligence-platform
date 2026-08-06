"""Tenant-admin role management schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from schemas.common import APIModel


class RoleCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value


class RoleResponse(APIModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class RoleListResponse(APIModel):
    items: list[RoleResponse]
    total: int
    page: int
    page_size: int
