"""Tenant-admin user management schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr, field_validator

from schemas.auth import RoleSummary
from schemas.common import APIModel


class UserCreateRequest(APIModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    password: SecretStr = Field(min_length=12, max_length=256)
    status: Literal["active", "inactive"] = "active"
    is_tenant_admin: bool = False


class UserResponse(APIModel):
    id: UUID
    email: str
    full_name: str | None
    status: str
    is_tenant_admin: bool
    roles: list[RoleSummary]
    created_at: datetime
    updated_at: datetime


class UserListResponse(APIModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class UserRoleAssignmentRequest(APIModel):
    role_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("role_ids")
    @classmethod
    def reject_duplicate_roles(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("role_ids must not contain duplicates")
        return value
