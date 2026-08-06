"""Tenant-administrator table and column permission APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.middleware import get_request_id
from core.tenant_context import TenantContext, require_tenant_admin
from schemas.permissions import (
    ColumnPermissionListResponse,
    ColumnPermissionReplaceRequest,
    TablePermissionCreateRequest,
    TablePermissionListResponse,
    TablePermissionResponse,
    TablePermissionUpdateRequest,
)
from services.permission_service import PermissionService

router = APIRouter(prefix="/permissions/tables", tags=["permissions"])


@router.post(
    "", response_model=TablePermissionResponse, status_code=status.HTTP_201_CREATED
)
async def create_table_permission(
    payload: TablePermissionCreateRequest,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TablePermissionResponse:
    return await PermissionService(session, context.tenant.id).create(
        payload, request_id=get_request_id(request)
    )


@router.get("", response_model=TablePermissionListResponse)
async def list_table_permissions(
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    connection_id: UUID | None = None,
    table_id: UUID | None = None,
    user_id: UUID | None = None,
    role_id: UUID | None = None,
) -> TablePermissionListResponse:
    return await PermissionService(session, context.tenant.id).list(
        page=page,
        page_size=page_size,
        connection_id=connection_id,
        table_id=table_id,
        user_id=user_id,
        role_id=role_id,
    )


@router.get("/{permission_id}", response_model=TablePermissionResponse)
async def get_table_permission(
    permission_id: UUID,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TablePermissionResponse:
    return await PermissionService(session, context.tenant.id).get(permission_id)


@router.put("/{permission_id}", response_model=TablePermissionResponse)
async def update_table_permission(
    permission_id: UUID,
    payload: TablePermissionUpdateRequest,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TablePermissionResponse:
    return await PermissionService(session, context.tenant.id).update(
        permission_id, payload, request_id=get_request_id(request)
    )


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table_permission(
    permission_id: UUID,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await PermissionService(session, context.tenant.id).delete(
        permission_id, request_id=get_request_id(request)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{permission_id}/columns", response_model=ColumnPermissionListResponse)
async def replace_column_permissions(
    permission_id: UUID,
    payload: ColumnPermissionReplaceRequest,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ColumnPermissionListResponse:
    return await PermissionService(session, context.tenant.id).replace_columns(
        permission_id, payload, request_id=get_request_id(request)
    )


@router.get("/{permission_id}/columns", response_model=ColumnPermissionListResponse)
async def get_column_permissions(
    permission_id: UUID,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ColumnPermissionListResponse:
    return await PermissionService(session, context.tenant.id).columns(permission_id)
