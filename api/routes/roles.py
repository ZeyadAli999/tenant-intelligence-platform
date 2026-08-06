"""Tenant-administrator role endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from core.tenant_context import TenantContext, require_tenant_admin
from schemas.roles import RoleCreateRequest, RoleListResponse, RoleResponse
from services.tenant_admin_service import TenantAdminService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoleResponse:
    return await TenantAdminService(session, context.tenant.id).create_role(
        name=payload.name,
        description=payload.description,
    )


@router.get("", response_model=RoleListResponse)
async def list_roles(
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoleListResponse:
    return await TenantAdminService(session, context.tenant.id).list_roles(
        page=page,
        page_size=page_size,
    )
