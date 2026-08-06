"""Tenant-administrator user endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from core.tenant_context import TenantContext, require_tenant_admin
from schemas.users import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserRoleAssignmentRequest,
)
from services.tenant_admin_service import TenantAdminService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    return await TenantAdminService(session, context.tenant.id).create_user(
        email=str(payload.email),
        full_name=payload.full_name,
        password=payload.password.get_secret_value(),
        status=payload.status,
        is_tenant_admin=payload.is_tenant_admin,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> UserListResponse:
    return await TenantAdminService(session, context.tenant.id).list_users(
        page=page,
        page_size=page_size,
    )


@router.put("/{user_id}/roles", response_model=UserResponse)
async def assign_roles(
    user_id: UUID,
    payload: UserRoleAssignmentRequest,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    return await TenantAdminService(session, context.tenant.id).assign_roles(
        user_id=user_id,
        role_ids=payload.role_ids,
    )
