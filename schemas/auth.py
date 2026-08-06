"""Authentication request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr

from schemas.common import APIModel


class LoginRequest(APIModel):
    tenant_code: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)


class RefreshRequest(APIModel):
    refresh_token: SecretStr = Field(min_length=1, max_length=8192)


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_in: int


class TenantSummary(APIModel):
    id: UUID
    name: str
    code: str
    status: str


class RoleSummary(APIModel):
    id: UUID
    name: str
    description: str | None


class CurrentUserResponse(APIModel):
    id: UUID
    email: str
    full_name: str | None
    status: str
    is_tenant_admin: bool
    tenant: TenantSummary
    roles: list[RoleSummary]
    created_at: datetime
