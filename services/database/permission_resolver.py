"""Single deterministic effective-permission resolver for all query paths."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    ColumnPermission,
    DatabaseColumn,
    DatabaseConnection,
    DatabaseSchema,
    DatabaseTable,
    TablePermission,
)
from repositories.permissions import PermissionRepository

MASK_STRENGTH = {None: 0, "partial": 1, "hash": 2, "redact": 3, "null": 4}


@dataclass(frozen=True)
class EffectiveColumn:
    metadata: DatabaseColumn
    readable: bool
    filterable: bool
    aggregatable: bool
    mask_type: str | None


@dataclass(frozen=True)
class EffectiveTable:
    metadata: DatabaseTable
    schema: DatabaseSchema
    columns: tuple[EffectiveColumn, ...]
    row_filters: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class EffectiveSchema:
    connection_id: UUID
    tables: tuple[EffectiveTable, ...]

    def table_by_qualified_name(self) -> dict[tuple[str, str], EffectiveTable]:
        return {
            (item.schema.schema_name, item.metadata.table_name): item
            for item in self.tables
        }


class PermissionResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PermissionRepository(session)

    async def resolve(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        role_ids: tuple[UUID, ...],
        connection_id: UUID,
    ) -> EffectiveSchema:
        connection = await self.session.scalar(
            select(DatabaseConnection).where(
                DatabaseConnection.tenant_id == tenant_id,
                DatabaseConnection.id == connection_id,
                DatabaseConnection.is_active.is_(True),
            )
        )
        if connection is None:
            return EffectiveSchema(connection_id=connection_id, tables=())
        permissions = await self.repository.effective_permissions(
            tenant_id, connection_id, user_id, role_ids
        )
        by_table: dict[UUID, list[TablePermission]] = {}
        for permission in permissions:
            by_table.setdefault(permission.table_id, []).append(permission)
        effective: list[EffectiveTable] = []
        for table_id, candidates in by_table.items():
            direct = [item for item in candidates if item.user_id == user_id]
            selected = (
                direct
                if direct
                else [item for item in candidates if item.role_id in role_ids]
            )
            selected = [item for item in selected if item.can_read]
            if not selected:
                continue
            table_row = await self.session.execute(
                select(DatabaseTable, DatabaseSchema)
                .join(DatabaseSchema, DatabaseSchema.id == DatabaseTable.schema_id)
                .where(
                    DatabaseTable.tenant_id == tenant_id,
                    DatabaseTable.connection_id == connection_id,
                    DatabaseTable.id == table_id,
                    DatabaseTable.is_enabled.is_(True),
                    DatabaseSchema.tenant_id == tenant_id,
                )
            )
            pair = table_row.one_or_none()
            if pair is None:
                continue
            table, schema = pair
            metadata_columns = await self.repository.table_columns(tenant_id, table.id)
            permission_columns = {
                permission.id: await self.repository.columns(tenant_id, permission.id)
                for permission in selected
            }
            columns = self._merge_columns(
                metadata_columns, selected, permission_columns
            )
            if not any(column.readable for column in columns):
                continue
            filters = self._merge_filters(selected)
            effective.append(
                EffectiveTable(
                    metadata=table,
                    schema=schema,
                    columns=tuple(columns),
                    row_filters=filters,
                )
            )
        effective.sort(
            key=lambda item: (item.schema.schema_name, item.metadata.table_name)
        )
        return EffectiveSchema(connection_id=connection_id, tables=tuple(effective))

    @staticmethod
    def _merge_columns(
        metadata_columns: list[DatabaseColumn],
        permissions: list[TablePermission],
        by_permission: dict[UUID, list[ColumnPermission]],
    ) -> list[EffectiveColumn]:
        result: list[EffectiveColumn] = []
        for column in metadata_columns:
            grants: list[tuple[bool, bool, bool, str | None]] = []
            for permission in permissions:
                explicit = by_permission[permission.id]
                if explicit:
                    item = next(
                        (row for row in explicit if row.column_id == column.id), None
                    )
                    if item is not None:
                        grants.append(
                            (
                                item.can_read,
                                item.can_filter,
                                item.can_aggregate,
                                item.mask_type,
                            )
                        )
                elif not column.is_sensitive:
                    grants.append((True, True, True, None))
            readable = any(item[0] for item in grants)
            filterable = any(item[1] for item in grants)
            aggregatable = any(item[2] for item in grants)
            masks = [item[3] for item in grants if item[0]]
            mask = max(masks, key=lambda value: MASK_STRENGTH[value]) if masks else None
            result.append(
                EffectiveColumn(
                    metadata=column,
                    readable=readable,
                    filterable=filterable,
                    aggregatable=aggregatable,
                    mask_type=mask,
                )
            )
        return result

    @staticmethod
    def _merge_filters(
        permissions: list[TablePermission],
    ) -> tuple[dict[str, object], ...]:
        if any(not item.row_filter for item in permissions):
            return ()
        return tuple(item.row_filter for item in permissions)
