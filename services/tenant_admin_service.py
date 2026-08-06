"""Tenant-isolated user, role, and role-assignment workflows."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, ResourceNotFoundError
from core.security import hash_password
from models import Role, User
from models.role import normalize_role_name
from models.user import normalize_email
from repositories.identity import IdentityRepository
from schemas.auth import RoleSummary
from schemas.roles import RoleListResponse, RoleResponse
from schemas.users import UserListResponse, UserResponse


def role_summary(role: Role) -> RoleSummary:
    return RoleSummary(id=role.id, name=role.name, description=role.description)


def role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
    )


def user_response(user: User, roles: list[Role]) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        is_tenant_admin=user.is_tenant_admin,
        roles=[role_summary(role) for role in roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class TenantAdminService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.repository = IdentityRepository(session)

    async def create_user(
        self,
        *,
        email: str,
        full_name: str | None,
        password: str,
        status: str,
        is_tenant_admin: bool,
    ) -> UserResponse:
        user = User(
            tenant_id=self.tenant_id,
            email=normalize_email(email),
            full_name=full_name.strip() if full_name else None,
            password_hash=hash_password(password),
            status=status,
            is_tenant_admin=is_tenant_admin,
        )
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(user)
        return user_response(user, [])

    async def list_users(self, *, page: int, page_size: int) -> UserListResponse:
        users, total = await self.repository.list_users(
            self.tenant_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        roles = await self.repository.get_roles_for_users(
            [user.id for user in users],
            self.tenant_id,
        )
        return UserListResponse(
            items=[user_response(user, roles[user.id]) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_role(
        self,
        *,
        name: str,
        description: str | None,
    ) -> RoleResponse:
        role = Role(
            tenant_id=self.tenant_id,
            name=normalize_role_name(name),
            description=description.strip() if description else None,
        )
        self.session.add(role)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(role)
        return role_response(role)

    async def list_roles(self, *, page: int, page_size: int) -> RoleListResponse:
        roles, total = await self.repository.list_roles(
            self.tenant_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return RoleListResponse(
            items=[role_response(role) for role in roles],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def assign_roles(
        self,
        *,
        user_id: UUID,
        role_ids: list[UUID],
    ) -> UserResponse:
        user = await self.repository.get_user(self.tenant_id, user_id)
        if user is None:
            raise ResourceNotFoundError
        roles = await self.repository.get_roles_by_ids(self.tenant_id, role_ids)
        if len(roles) != len(role_ids):
            raise ResourceNotFoundError
        await self.repository.replace_user_roles(user.id, self.tenant_id, role_ids)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ResourceNotFoundError from exc
        return user_response(user, sorted(roles, key=lambda role: role.name))
