"""Identity fixtures shared by Phase 2 unit tests."""

from dataclasses import dataclass
from uuid import uuid4

from core.security import hash_password
from models import Role, Tenant, User, UserRole
from tests.unit.conftest import DatabaseHarness


@dataclass(frozen=True)
class SeededIdentity:
    tenant: Tenant
    user: User
    password: str
    roles: tuple[Role, ...]


async def seed_identity(
    database: DatabaseHarness,
    *,
    tenant_code: str = "acme",
    tenant_name: str = "Acme Company",
    tenant_status: str = "active",
    email: str = "admin@acme.example",
    password: str = "Correct-Horse-Battery-99",
    user_status: str = "active",
    is_tenant_admin: bool = True,
    role_names: tuple[str, ...] = ("administrator",),
) -> SeededIdentity:
    tenant = Tenant(
        id=uuid4(),
        name=tenant_name,
        code=tenant_code,
        status=tenant_status,
    )
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Test User",
        password_hash=hash_password(password),
        status=user_status,
        is_tenant_admin=is_tenant_admin,
    )
    roles = tuple(
        Role(id=uuid4(), tenant_id=tenant.id, name=name) for name in role_names
    )
    assignments = [
        UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id)
        for role in roles
    ]
    async with database.sessions() as session:
        session.add(tenant)
        await session.flush()
        session.add_all([user, *roles])
        await session.flush()
        session.add_all(assignments)
        await session.commit()
    return SeededIdentity(tenant=tenant, user=user, password=password, roles=roles)


async def login(
    client: object,
    identity: SeededIdentity,
) -> dict[str, object]:
    response = await client.post(  # type: ignore[attr-defined]
        "/api/auth/login",
        json={
            "tenant_code": identity.tenant.code,
            "email": identity.user.email,
            "password": identity.password,
        },
    )
    assert response.status_code == 200
    return response.json()


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
