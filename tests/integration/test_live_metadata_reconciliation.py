"""Live PostgreSQL proof that repeated discovery preserves metadata UUIDs."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.security import hash_password
from models import (
    DatabaseColumn,
    DatabaseConnection,
    DatabaseSchema,
    DatabaseTable,
    Tenant,
    User,
)
from repositories.database_connections import DatabaseConnectionRepository
from tests.integration.test_customer_postgresql import (
    customer_parameters,
    integration_adapter,
)
from tests.integration.test_migrations import run_alembic

pytestmark = pytest.mark.integration


async def metadata_ids(
    session: object, tenant_id: object, connection_id: object
) -> tuple[set[object], set[object], set[object]]:
    schemas = set(
        (
            await session.scalars(  # type: ignore[attr-defined]
                select(DatabaseSchema.id).where(
                    DatabaseSchema.tenant_id == tenant_id,
                    DatabaseSchema.connection_id == connection_id,
                )
            )
        ).all()
    )
    tables = set(
        (
            await session.scalars(  # type: ignore[attr-defined]
                select(DatabaseTable.id).where(
                    DatabaseTable.tenant_id == tenant_id,
                    DatabaseTable.connection_id == connection_id,
                )
            )
        ).all()
    )
    columns = set(
        (
            await session.scalars(  # type: ignore[attr-defined]
                select(DatabaseColumn.id).where(
                    DatabaseColumn.tenant_id == tenant_id,
                    DatabaseColumn.table_id.in_(tables),
                )
            )
        ).all()
    )
    return schemas, tables, columns


@pytest.mark.asyncio
async def test_repeated_live_postgresql_discovery_preserves_metadata_ids(
    postgres_test_url: str,
) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    parameters = customer_parameters()
    adapter, validator = integration_adapter()
    discovered = await adapter.discover_schema(parameters, validator)
    engine = create_async_engine(postgres_test_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = uuid4()
    user_id = uuid4()
    connection_id = uuid4()
    async with sessions() as session:
        session.add(
            Tenant(
                id=tenant_id,
                name="Live Reconcile",
                code=f"live-reconcile-{uuid4().hex}",
            )
        )
        await session.flush()
        session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"live-reconcile-{uuid4().hex}@example.com",
                password_hash=hash_password("Integration-Password-Strong-99"),
            )
        )
        await session.flush()
        session.add(
            DatabaseConnection(
                id=connection_id,
                tenant_id=tenant_id,
                created_by=user_id,
                name="live-customer",
                database_type="postgresql",
                host="8.8.8.8",
                port=5432,
                database_name="customer",
                username="reader",
                encrypted_password="v1.nonce.ciphertext",
            )
        )
        await session.commit()
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=tenant_id,
            connection_id=connection_id,
            discovered=discovered,
        )
        await session.commit()
        first = await metadata_ids(session, tenant_id, connection_id)
        await repository.reconcile_metadata(
            tenant_id=tenant_id,
            connection_id=connection_id,
            discovered=await adapter.discover_schema(parameters, validator),
        )
        await session.commit()
        second = await metadata_ids(session, tenant_id, connection_id)
        assert all(first)
        assert second == first
        await session.delete(await session.get(Tenant, tenant_id))
        await session.commit()
    await engine.dispose()
