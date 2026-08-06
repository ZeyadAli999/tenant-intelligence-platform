"""Database constraint and normalization tests on the fast test database."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from core.security import hash_password
from models import Role, Tenant, User, UserRole
from tests.unit.conftest import DatabaseHarness


@pytest.mark.asyncio
async def test_email_normalization_and_tenant_scoped_uniqueness(
    test_database: DatabaseHarness,
) -> None:
    tenant_a = Tenant(id=uuid4(), name="A", code="a")
    tenant_b = Tenant(id=uuid4(), name="B", code="b")
    user_a = User(
        id=uuid4(),
        tenant_id=tenant_a.id,
        email=" Shared@Example.com ",
        password_hash=hash_password("User-Password-Strong-99"),
    )
    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email="shared@example.com",
        password_hash=hash_password("User-Password-Strong-99"),
    )
    async with test_database.sessions() as session:
        session.add_all([tenant_a, tenant_b, user_a, user_b])
        await session.commit()
        assert user_a.email == "shared@example.com"

        session.add(
            User(
                tenant_id=tenant_a.id,
                email="SHARED@example.com",
                password_hash=hash_password("User-Password-Strong-99"),
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_database_rejects_cross_tenant_role_assignment(
    test_database: DatabaseHarness,
) -> None:
    tenant_a = Tenant(id=uuid4(), name="A", code="a")
    tenant_b = Tenant(id=uuid4(), name="B", code="b")
    user_a = User(
        id=uuid4(),
        tenant_id=tenant_a.id,
        email="user@a.example",
        password_hash=hash_password("User-Password-Strong-99"),
    )
    role_b = Role(id=uuid4(), tenant_id=tenant_b.id, name="analyst")
    async with test_database.sessions() as session:
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all([user_a, role_b])
        await session.commit()
        session.add(
            UserRole(
                user_id=user_a.id,
                role_id=role_b.id,
                tenant_id=tenant_a.id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
