"""Tenant-admin permission management with normalized row authorization."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, InvalidPermissionError, ResourceNotFoundError
from models import ColumnPermission, TablePermission
from repositories.permissions import PermissionRepository
from schemas.permissions import (
    ColumnPermissionListResponse,
    ColumnPermissionReplaceRequest,
    ColumnPermissionResponse,
    TablePermissionCreateRequest,
    TablePermissionListResponse,
    TablePermissionResponse,
    TablePermissionUpdateRequest,
)
from services.database.row_filter import validate_row_filter

logger = logging.getLogger(__name__)


class PermissionService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.repository = PermissionRepository(session)

    async def create(
        self, payload: TablePermissionCreateRequest, *, request_id: str
    ) -> TablePermissionResponse:
        if (
            payload.user_id is not None
            and await self.repository.get_user(self.tenant_id, payload.user_id) is None
        ):
            raise ResourceNotFoundError
        if (
            payload.role_id is not None
            and await self.repository.get_role(self.tenant_id, payload.role_id) is None
        ):
            raise ResourceNotFoundError
        table = await self.repository.get_table(
            self.tenant_id, payload.connection_id, payload.table_id
        )
        if table is None:
            raise ResourceNotFoundError
        columns = await self.repository.table_columns(self.tenant_id, table.id)
        normalized_filter = validate_row_filter(
            payload.row_filter, columns=columns, explicit_permissions=[]
        )
        permission = TablePermission(
            id=uuid4(),
            tenant_id=self.tenant_id,
            role_id=payload.role_id,
            user_id=payload.user_id,
            connection_id=payload.connection_id,
            table_id=payload.table_id,
            can_read=payload.can_read,
            can_insert=False,
            can_update=False,
            can_delete=False,
            row_filter=normalized_filter,
        )
        self.session.add(permission)
        await self._commit_conflict()
        logger.info(
            "Permission created request_id=%r permission_id=%s",
            request_id,
            permission.id,
        )
        return TablePermissionResponse.model_validate(permission)

    async def get(self, permission_id: UUID) -> TablePermissionResponse:
        return TablePermissionResponse.model_validate(
            await self._permission(permission_id)
        )

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        connection_id: UUID | None,
        table_id: UUID | None,
        user_id: UUID | None,
        role_id: UUID | None,
    ) -> TablePermissionListResponse:
        rows, total = await self.repository.list_permissions(
            self.tenant_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            connection_id=connection_id,
            table_id=table_id,
            user_id=user_id,
            role_id=role_id,
        )
        return TablePermissionListResponse(
            items=[TablePermissionResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(
        self,
        permission_id: UUID,
        payload: TablePermissionUpdateRequest,
        *,
        request_id: str,
    ) -> TablePermissionResponse:
        permission = await self._permission(permission_id)
        if "can_read" in payload.model_fields_set and payload.can_read is not None:
            permission.can_read = payload.can_read
        if "row_filter" in payload.model_fields_set:
            columns = await self.repository.table_columns(
                self.tenant_id, permission.table_id
            )
            explicit = await self.repository.columns(self.tenant_id, permission.id)
            permission.row_filter = validate_row_filter(
                payload.row_filter, columns=columns, explicit_permissions=explicit
            )
        await self.session.commit()
        logger.info(
            "Permission updated request_id=%r permission_id=%s",
            request_id,
            permission.id,
        )
        return TablePermissionResponse.model_validate(permission)

    async def delete(self, permission_id: UUID, *, request_id: str) -> None:
        permission = await self._permission(permission_id)
        await self.session.delete(permission)
        await self.session.commit()
        logger.info(
            "Permission deleted request_id=%r permission_id=%s",
            request_id,
            permission_id,
        )

    async def replace_columns(
        self,
        permission_id: UUID,
        payload: ColumnPermissionReplaceRequest,
        *,
        request_id: str,
    ) -> ColumnPermissionListResponse:
        permission = await self._permission(permission_id)
        table_columns = await self.repository.table_columns(
            self.tenant_id, permission.table_id
        )
        allowed_ids = {column.id for column in table_columns}
        if any(item.column_id not in allowed_ids for item in payload.items):
            raise ResourceNotFoundError
        metadata_by_id = {column.id: column for column in table_columns}
        if any(
            metadata_by_id[item.column_id].is_sensitive
            and item.can_read
            and item.mask_type is None
            for item in payload.items
        ):
            raise InvalidPermissionError
        rows = [
            ColumnPermission(
                id=uuid4(),
                tenant_id=self.tenant_id,
                table_id=permission.table_id,
                table_permission_id=permission.id,
                column_id=item.column_id,
                can_read=item.can_read,
                can_filter=item.can_filter,
                can_aggregate=item.can_aggregate,
                mask_type=item.mask_type,
            )
            for item in payload.items
        ]
        if permission.row_filter:
            from schemas.permissions import RowFilterDSL

            validate_row_filter(
                RowFilterDSL.model_validate(permission.row_filter),
                columns=table_columns,
                explicit_permissions=rows,
            )
        try:
            await self.repository.replace_columns(permission, rows)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        logger.info(
            "Column permissions replaced request_id=%r permission_id=%s",
            request_id,
            permission.id,
        )
        return ColumnPermissionListResponse(
            items=[ColumnPermissionResponse.model_validate(row) for row in rows]
        )

    async def columns(self, permission_id: UUID) -> ColumnPermissionListResponse:
        permission = await self._permission(permission_id)
        rows = await self.repository.columns(self.tenant_id, permission.id)
        return ColumnPermissionListResponse(
            items=[ColumnPermissionResponse.model_validate(row) for row in rows]
        )

    async def _permission(self, permission_id: UUID) -> TablePermission:
        permission = await self.repository.get_permission(self.tenant_id, permission_id)
        if permission is None:
            raise ResourceNotFoundError
        return permission

    async def _commit_conflict(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
