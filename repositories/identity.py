"""Tenant-scoped identity persistence operations."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import RefreshToken, Role, Tenant, User, UserRole


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tenant_by_code(self, code: str) -> Tenant | None:
        return await self.session.scalar(select(Tenant).where(Tenant.code == code))

    async def get_user_by_email(self, tenant_id: UUID, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tenant_id == tenant_id, User.email == email)
        )

    async def get_identity(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> tuple[User, Tenant] | None:
        row = (
            await self.session.execute(
                select(User, Tenant)
                .join(Tenant, Tenant.id == User.tenant_id)
                .where(User.id == user_id, User.tenant_id == tenant_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def get_roles_for_user(self, user_id: UUID, tenant_id: UUID) -> list[Role]:
        return list(
            (
                await self.session.scalars(
                    select(Role)
                    .join(
                        UserRole,
                        (UserRole.role_id == Role.id)
                        & (UserRole.tenant_id == Role.tenant_id),
                    )
                    .where(
                        UserRole.user_id == user_id,
                        UserRole.tenant_id == tenant_id,
                    )
                    .order_by(Role.name)
                )
            ).all()
        )

    async def get_roles_for_users(
        self,
        user_ids: Sequence[UUID],
        tenant_id: UUID,
    ) -> dict[UUID, list[Role]]:
        roles_by_user = {user_id: [] for user_id in user_ids}
        if not user_ids:
            return roles_by_user
        rows = (
            await self.session.execute(
                select(UserRole.user_id, Role)
                .join(
                    Role,
                    (Role.id == UserRole.role_id)
                    & (Role.tenant_id == UserRole.tenant_id),
                )
                .where(
                    UserRole.tenant_id == tenant_id,
                    UserRole.user_id.in_(user_ids),
                )
                .order_by(Role.name)
            )
        ).all()
        for user_id, role in rows:
            roles_by_user[user_id].append(role)
        return roles_by_user

    async def get_refresh_token(
        self,
        jti: UUID,
        *,
        for_update: bool = False,
    ) -> RefreshToken | None:
        statement = select(RefreshToken).where(RefreshToken.jti == jti)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def revoke_refresh_family(
        self,
        family_id: UUID,
        revoked_at: datetime,
    ) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def get_user(self, tenant_id: UUID, user_id: UUID) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tenant_id == tenant_id, User.id == user_id)
        )

    async def list_users(
        self,
        tenant_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[User], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
        )
        users = list(
            (
                await self.session.scalars(
                    select(User)
                    .where(User.tenant_id == tenant_id)
                    .order_by(User.created_at, User.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return users, int(total or 0)

    async def get_role(self, tenant_id: UUID, role_id: UUID) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.id == role_id)
        )

    async def get_roles_by_ids(
        self,
        tenant_id: UUID,
        role_ids: Sequence[UUID],
    ) -> list[Role]:
        if not role_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(Role).where(
                        Role.tenant_id == tenant_id,
                        Role.id.in_(role_ids),
                    )
                )
            ).all()
        )

    async def list_roles(
        self,
        tenant_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Role], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(Role).where(Role.tenant_id == tenant_id)
        )
        roles = list(
            (
                await self.session.scalars(
                    select(Role)
                    .where(Role.tenant_id == tenant_id)
                    .order_by(Role.name, Role.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return roles, int(total or 0)

    async def replace_user_roles(
        self,
        user_id: UUID,
        tenant_id: UUID,
        role_ids: Sequence[UUID],
    ) -> None:
        await self.session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.tenant_id == tenant_id,
            )
        )
        self.session.add_all(
            UserRole(user_id=user_id, role_id=role_id, tenant_id=tenant_id)
            for role_id in role_ids
        )
