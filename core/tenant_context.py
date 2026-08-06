"""Verified, database-backed tenant context dependencies."""

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.exceptions import AuthenticationError, AuthorizationError
from app.middleware import get_request_id
from core.security import decode_token
from models import EntityStatus, Role, Tenant, User
from repositories.identity import IdentityRepository

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


@dataclass(frozen=True)
class TenantContext:
    user: User
    tenant: Tenant
    roles: tuple[Role, ...]

    @property
    def is_tenant_admin(self) -> bool:
        return self.user.is_tenant_admin


async def get_tenant_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> TenantContext:
    """Resolve tenant identity only from a verified access token and database rows."""
    request_id = get_request_id(request)
    try:
        if token is None:
            raise AuthenticationError
        claims = decode_token(token, expected_type="access")
        repository = IdentityRepository(session)
        identity = await repository.get_identity(claims.user_id, claims.tenant_id)
        if identity is None:
            raise AuthenticationError
        user, tenant = identity
        if (
            user.status != EntityStatus.ACTIVE.value
            or tenant.status != EntityStatus.ACTIVE.value
            or user.tenant_id != tenant.id
        ):
            raise AuthenticationError
        roles = await repository.get_roles_for_user(user.id, tenant.id)
        return TenantContext(user=user, tenant=tenant, roles=tuple(roles))
    except AuthenticationError:
        logger.info("Access authentication rejected request_id=%r", request_id)
        raise


async def require_tenant_admin(
    request: Request,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    """Require tenant-administrator authority within the verified tenant."""
    if not context.is_tenant_admin:
        logger.info(
            "Tenant administrator authorization rejected request_id=%r",
            get_request_id(request),
        )
        raise AuthorizationError
    return context
