"""Tenant-isolated runtime database connection and metadata endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.middleware import get_request_id
from core.tenant_context import TenantContext, get_tenant_context, require_tenant_admin
from schemas.database_connections import (
    ConnectionTestResponse,
    DatabaseConnectionCreateRequest,
    DatabaseConnectionListResponse,
    DatabaseConnectionResponse,
    DatabaseConnectionUpdateRequest,
    DatabaseSchemaListResponse,
    DatabaseTableListResponse,
    SchemaSyncResponse,
)
from schemas.permissions import AllowedSchemaResponse
from services.database.allowed_schema import allowed_schema_response
from services.database.connection_service import DatabaseConnectionService
from services.database.permission_resolver import PermissionResolver

router = APIRouter(prefix="/database-connections", tags=["database-connections"])


@router.get("/{connection_id}/allowed-schema", response_model=AllowedSchemaResponse)
async def get_allowed_schema(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AllowedSchemaResponse:
    await DatabaseConnectionService(session, context.tenant.id).get(connection_id)
    effective = await PermissionResolver(session).resolve(
        tenant_id=context.tenant.id,
        user_id=context.user.id,
        role_ids=tuple(role.id for role in context.roles),
        connection_id=connection_id,
    )
    return allowed_schema_response(effective)


@router.post(
    "",
    response_model=DatabaseConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_database_connection(
    payload: DatabaseConnectionCreateRequest,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseConnectionResponse:
    return await DatabaseConnectionService(session, context.tenant.id).create(
        payload,
        created_by=context.user.id,
    )


@router.get("", response_model=DatabaseConnectionListResponse)
async def list_database_connections(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DatabaseConnectionListResponse:
    return await DatabaseConnectionService(session, context.tenant.id).list(
        page=page,
        page_size=page_size,
    )


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_database_connection(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseConnectionResponse:
    return await DatabaseConnectionService(session, context.tenant.id).get(
        connection_id
    )


@router.put("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_database_connection(
    connection_id: UUID,
    payload: DatabaseConnectionUpdateRequest,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseConnectionResponse:
    return await DatabaseConnectionService(session, context.tenant.id).update(
        connection_id,
        payload,
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database_connection(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await DatabaseConnectionService(session, context.tenant.id).delete(connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_database_connection(
    connection_id: UUID,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConnectionTestResponse:
    return await DatabaseConnectionService(
        session,
        context.tenant.id,
    ).test_connection(connection_id, request_id=get_request_id(request))


@router.post("/{connection_id}/sync-schema", response_model=SchemaSyncResponse)
async def sync_database_schema(
    connection_id: UUID,
    request: Request,
    context: Annotated[TenantContext, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SchemaSyncResponse:
    return await DatabaseConnectionService(session, context.tenant.id).sync_schema(
        connection_id,
        request_id=get_request_id(request),
    )


@router.get("/{connection_id}/schemas", response_model=DatabaseSchemaListResponse)
async def list_database_schemas(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DatabaseSchemaListResponse:
    return await DatabaseConnectionService(session, context.tenant.id).list_schemas(
        connection_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{connection_id}/tables", response_model=DatabaseTableListResponse)
async def list_database_tables(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    schema_name: Annotated[str | None, Query(max_length=255)] = None,
    enabled: bool | None = None,
    table_type: Literal["table", "view"] | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> DatabaseTableListResponse:
    return await DatabaseConnectionService(session, context.tenant.id).list_tables(
        connection_id,
        page=page,
        page_size=page_size,
        schema_name=schema_name,
        enabled=enabled,
        table_type=table_type,
        search=search,
    )
