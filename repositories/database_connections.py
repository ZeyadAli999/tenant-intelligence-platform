"""Tenant-scoped persistence for runtime connections and cached metadata."""

from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DatabaseColumn, DatabaseConnection, DatabaseSchema, DatabaseTable
from services.database.adapters.base import DiscoveredSchema


class DatabaseConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_connection(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        *,
        active_only: bool = True,
    ) -> DatabaseConnection | None:
        statement = select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == tenant_id,
            DatabaseConnection.id == connection_id,
        )
        if active_only:
            statement = statement.where(DatabaseConnection.is_active.is_(True))
        return await self.session.scalar(statement)

    async def list_connections(
        self,
        tenant_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[DatabaseConnection], int]:
        active = (
            DatabaseConnection.tenant_id == tenant_id,
            DatabaseConnection.is_active.is_(True),
        )
        total = await self.session.scalar(
            select(func.count()).select_from(DatabaseConnection).where(*active)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(DatabaseConnection)
                    .where(*active)
                    .order_by(DatabaseConnection.name, DatabaseConnection.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def list_schemas(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[DatabaseSchema], int]:
        scope = (
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
        total = await self.session.scalar(
            select(func.count()).select_from(DatabaseSchema).where(*scope)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(DatabaseSchema)
                    .where(*scope)
                    .order_by(DatabaseSchema.schema_name, DatabaseSchema.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def list_tables(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        *,
        offset: int,
        limit: int,
        schema_name: str | None,
        enabled: bool | None,
        table_type: str | None,
        search: str | None,
    ) -> tuple[list[tuple[DatabaseTable, DatabaseSchema]], int]:
        filters = [
            DatabaseTable.tenant_id == tenant_id,
            DatabaseTable.connection_id == connection_id,
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
            DatabaseTable.schema_id == DatabaseSchema.id,
        ]
        if schema_name is not None:
            filters.append(DatabaseSchema.schema_name == schema_name)
        if enabled is not None:
            filters.append(DatabaseTable.is_enabled == enabled)
        if table_type is not None:
            filters.append(DatabaseTable.table_type == table_type)
        if search is not None:
            filters.append(DatabaseTable.table_name.contains(search, autoescape=True))
        total = await self.session.scalar(
            select(func.count())
            .select_from(DatabaseTable)
            .join(DatabaseSchema, DatabaseSchema.id == DatabaseTable.schema_id)
            .where(*filters)
        )
        rows = list(
            (
                await self.session.execute(
                    select(DatabaseTable, DatabaseSchema)
                    .join(DatabaseSchema, DatabaseSchema.id == DatabaseTable.schema_id)
                    .where(*filters)
                    .order_by(
                        DatabaseSchema.schema_name,
                        DatabaseTable.table_name,
                        DatabaseTable.id,
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def columns_for_tables(
        self,
        tenant_id: UUID,
        table_ids: Sequence[UUID],
    ) -> dict[UUID, list[DatabaseColumn]]:
        result = {table_id: [] for table_id in table_ids}
        if not table_ids:
            return result
        columns = list(
            (
                await self.session.scalars(
                    select(DatabaseColumn)
                    .where(
                        DatabaseColumn.tenant_id == tenant_id,
                        DatabaseColumn.table_id.in_(table_ids),
                    )
                    .order_by(
                        DatabaseColumn.table_id,
                        DatabaseColumn.ordinal_position,
                        DatabaseColumn.id,
                    )
                )
            ).all()
        )
        for column in columns:
            result[column.table_id].append(column)
        return result

    async def reconcile_metadata(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        discovered: tuple[DiscoveredSchema, ...],
    ) -> tuple[int, int, int]:
        await self.session.scalar(
            select(DatabaseConnection.id)
            .where(
                DatabaseConnection.tenant_id == tenant_id,
                DatabaseConnection.id == connection_id,
            )
            .with_for_update()
        )
        schemas = list(
            (
                await self.session.scalars(
                    select(DatabaseSchema).where(
                        DatabaseSchema.tenant_id == tenant_id,
                        DatabaseSchema.connection_id == connection_id,
                    )
                )
            ).all()
        )
        tables = list(
            (
                await self.session.scalars(
                    select(DatabaseTable).where(
                        DatabaseTable.tenant_id == tenant_id,
                        DatabaseTable.connection_id == connection_id,
                    )
                )
            ).all()
        )
        table_ids = [table.id for table in tables]
        columns = (
            list(
                (
                    await self.session.scalars(
                        select(DatabaseColumn).where(
                            DatabaseColumn.tenant_id == tenant_id,
                            DatabaseColumn.table_id.in_(table_ids),
                        )
                    )
                ).all()
            )
            if table_ids
            else []
        )
        schemas_by_name = {schema.schema_name: schema for schema in schemas}
        tables_by_key = {(table.schema_id, table.table_name): table for table in tables}
        columns_by_key = {
            (column.table_id, column.column_name): column for column in columns
        }
        seen_schema_ids: set[UUID] = set()
        seen_table_ids: set[UUID] = set()
        schema_count = table_count = column_count = 0
        for discovered_schema in discovered:
            schema = schemas_by_name.get(discovered_schema.name)
            if schema is None:
                schema = DatabaseSchema(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    schema_name=discovered_schema.name,
                )
                self.session.add(schema)
                await self.session.flush([schema])
                schemas_by_name[schema.schema_name] = schema
            schema.description = discovered_schema.description
            seen_schema_ids.add(schema.id)
            schema_count += 1
            for discovered_table in discovered_schema.tables:
                table = tables_by_key.get((schema.id, discovered_table.name))
                if table is None:
                    table = DatabaseTable(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        connection_id=connection_id,
                        schema_id=schema.id,
                        table_name=discovered_table.name,
                        metadata_json={},
                    )
                    self.session.add(table)
                    await self.session.flush([table])
                    tables_by_key[(schema.id, table.table_name)] = table
                table.table_type = discovered_table.table_type
                table.description = discovered_table.description
                table.estimated_row_count = discovered_table.estimated_row_count
                table.primary_key_columns = list(discovered_table.primary_key_columns)
                table.is_enabled = True
                seen_table_ids.add(table.id)
                table_count += 1
                seen_column_names: set[str] = set()
                for discovered_column in discovered_table.columns:
                    column = columns_by_key.get((table.id, discovered_column.name))
                    if column is None:
                        column = DatabaseColumn(
                            id=uuid4(),
                            tenant_id=tenant_id,
                            table_id=table.id,
                            column_name=discovered_column.name,
                            sample_values=[],
                        )
                        self.session.add(column)
                        columns_by_key[(table.id, column.column_name)] = column
                    column.data_type = discovered_column.data_type
                    column.ordinal_position = discovered_column.ordinal_position
                    column.is_nullable = discovered_column.is_nullable
                    column.is_primary_key = discovered_column.is_primary_key
                    column.is_foreign_key = discovered_column.is_foreign_key
                    column.referenced_schema = discovered_column.referenced_schema
                    column.referenced_table = discovered_column.referenced_table
                    column.referenced_column = discovered_column.referenced_column
                    column.description = discovered_column.description
                    seen_column_names.add(column.column_name)
                    column_count += 1
                stale_column_ids = [
                    column.id
                    for column in columns
                    if column.table_id == table.id
                    and column.column_name not in seen_column_names
                ]
                if stale_column_ids:
                    await self.session.execute(
                        delete(DatabaseColumn).where(
                            DatabaseColumn.tenant_id == tenant_id,
                            DatabaseColumn.table_id == table.id,
                            DatabaseColumn.id.in_(stale_column_ids),
                        )
                    )
        for table in tables:
            if table.id not in seen_table_ids:
                table.is_enabled = False
        stale_empty_schema_ids = [
            schema.id
            for schema in schemas
            if schema.id not in seen_schema_ids
            and not any(table.schema_id == schema.id for table in tables)
        ]
        if stale_empty_schema_ids:
            await self.session.execute(
                delete(DatabaseSchema).where(
                    DatabaseSchema.tenant_id == tenant_id,
                    DatabaseSchema.connection_id == connection_id,
                    DatabaseSchema.id.in_(stale_empty_schema_ids),
                )
            )
        await self.session.flush()
        return schema_count, table_count, column_count
