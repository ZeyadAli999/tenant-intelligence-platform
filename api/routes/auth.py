"""Authentication endpoints required by the assignment."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.middleware import get_request_id
from core.tenant_context import TenantContext, get_tenant_context
from schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RoleSummary,
    TenantSummary,
    TokenResponse,
)
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    tokens = await AuthService(session).login(
        tenant_code=payload.tenant_code,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        request_id=get_request_id(request),
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_token_expires_in=tokens.access_token_expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    tokens = await AuthService(session).rotate_refresh_token(
        raw_refresh_token=payload.refresh_token.get_secret_value(),
        request_id=get_request_id(request),
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_token_expires_in=tokens.access_token_expires_in,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=context.user.id,
        email=context.user.email,
        full_name=context.user.full_name,
        status=context.user.status,
        is_tenant_admin=context.is_tenant_admin,
        tenant=TenantSummary(
            id=context.tenant.id,
            name=context.tenant.name,
            code=context.tenant.code,
            status=context.tenant.status,
        ),
        roles=[
            RoleSummary(id=role.id, name=role.name, description=role.description)
            for role in context.roles
        ],
        created_at=context.user.created_at,
    )
