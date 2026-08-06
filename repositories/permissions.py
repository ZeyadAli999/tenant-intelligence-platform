"""Tenant-scoped permission persistence."""

from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    ColumnPermission,
    DatabaseColumn,
    DatabaseConnection,
    DatabaseTable,
    Role,
    TablePermission,
    User,
)


class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user(self, tenant_id: UUID, user_id: UUID) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tenant_id == tenant_id, User.id == user_id)
        )

    async def get_role(self, tenant_id: UUID, role_id: UUID) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.id == role_id)
        )

    async def get_table(
        self, tenant_id: UUID, connection_id: UUID, table_id: UUID
    ) -> DatabaseTable | None:
        return await self.session.scalar(
            select(DatabaseTable)
            .join(
                DatabaseConnection, DatabaseConnection.id == DatabaseTable.connection_id
            )
            .where(
                DatabaseTable.tenant_id == tenant_id,
                DatabaseTable.connection_id == connection_id,
                DatabaseTable.id == table_id,
                DatabaseConnection.tenant_id == tenant_id,
                DatabaseConnection.is_active.is_(True),
            )
        )

    async def get_permission(
        self, tenant_id: UUID, permission_id: UUID
    ) -> TablePermission | None:
        return await self.session.scalar(
            select(TablePermission).where(
                TablePermission.tenant_id == tenant_id,
                TablePermission.id == permission_id,
            )
        )

    async def list_permissions(
        self,
        tenant_id: UUID,
        *,
        offset: int,
        limit: int,
        connection_id: UUID | None,
        table_id: UUID | None,
        user_id: UUID | None,
        role_id: UUID | None,
    ) -> tuple[list[TablePermission], int]:
        filters = [TablePermission.tenant_id == tenant_id]
        for field, value in (
            (TablePermission.connection_id, connection_id),
            (TablePermission.table_id, table_id),
            (TablePermission.user_id, user_id),
            (TablePermission.role_id, role_id),
        ):
            if value is not None:
                filters.append(field == value)
        total = await self.session.scalar(
            select(func.count()).select_from(TablePermission).where(*filters)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(TablePermission)
                    .where(*filters)
                    .order_by(TablePermission.created_at, TablePermission.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def columns(
        self, tenant_id: UUID, table_permission_id: UUID
    ) -> list[ColumnPermission]:
        return list(
            (
                await self.session.scalars(
                    select(ColumnPermission)
                    .where(
                        ColumnPermission.tenant_id == tenant_id,
                        ColumnPermission.table_permission_id == table_permission_id,
                    )
                    .order_by(ColumnPermission.column_id)
                )
            ).all()
        )

    async def table_columns(
        self, tenant_id: UUID, table_id: UUID
    ) -> list[DatabaseColumn]:
        return list(
            (
                await self.session.scalars(
                    select(DatabaseColumn).where(
                        DatabaseColumn.tenant_id == tenant_id,
                        DatabaseColumn.table_id == table_id,
                    )
                )
            ).all()
        )

    async def replace_columns(
        self, permission: TablePermission, rows: list[ColumnPermission]
    ) -> None:
        await self.session.execute(
            delete(ColumnPermission).where(
                ColumnPermission.tenant_id == permission.tenant_id,
                ColumnPermission.table_permission_id == permission.id,
            )
        )
        self.session.add_all(rows)
        await self.session.flush()

    async def effective_permissions(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        user_id: UUID,
        role_ids: tuple[UUID, ...],
    ) -> list[TablePermission]:
        subject = TablePermission.user_id == user_id
        if role_ids:
            subject = or_(subject, TablePermission.role_id.in_(role_ids))
        return list(
            (
                await self.session.scalars(
                    select(TablePermission).where(
                        TablePermission.tenant_id == tenant_id,
                        TablePermission.connection_id == connection_id,
                        subject,
                    )
                )
            ).all()
        )
