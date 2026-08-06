"""Live PostgreSQL uniqueness, foreign-key, and tenant-isolation constraints."""

from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.security import hash_password
from models import Role, Tenant, User, UserRole
from tests.integration.test_migrations import run_alembic

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgresql_identity_constraints(postgres_test_url: str) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    engine = create_async_engine(postgres_test_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_a = Tenant(id=uuid4(), name="Integration A", code=f"a-{uuid4().hex}")
    tenant_b = Tenant(id=uuid4(), name="Integration B", code=f"b-{uuid4().hex}")
    user_a = User(
        id=uuid4(),
        tenant_id=tenant_a.id,
        email="shared@integration.example",
        password_hash=hash_password("Integration-Password-Strong-99"),
    )
    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email="shared@integration.example",
        password_hash=hash_password("Integration-Password-Strong-99"),
    )
    role_b = Role(id=uuid4(), tenant_id=tenant_b.id, name="integration-role")
    tenant_ids = [tenant_a.id, tenant_b.id]
    user_a_id = user_a.id
    role_b_id = role_b.id

    async with sessions() as session:
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all([user_a, user_b, role_b])
        await session.commit()

        session.add(
            User(
                tenant_id=tenant_a.id,
                email=user_a.email,
                password_hash=hash_password("Integration-Password-Strong-99"),
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        session.add(
            UserRole(
                user_id=user_a_id,
                role_id=role_b_id,
                tenant_id=tenant_ids[0],
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
        await session.commit()
    await engine.dispose()
