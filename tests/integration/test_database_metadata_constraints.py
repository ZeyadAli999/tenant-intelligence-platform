"""Live PostgreSQL tenant constraints for connection metadata."""

from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
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
from tests.integration.test_migrations import run_alembic

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgresql_metadata_tenant_constraints(postgres_test_url: str) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    engine = create_async_engine(postgres_test_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_a = Tenant(id=uuid4(), name="Metadata A", code=f"metadata-a-{uuid4().hex}")
    tenant_b = Tenant(id=uuid4(), name="Metadata B", code=f"metadata-b-{uuid4().hex}")
    user_a = User(
        id=uuid4(),
        tenant_id=tenant_a.id,
        email=f"metadata-a-{uuid4().hex}@example.test",
        password_hash=hash_password("Integration-Password-Strong-99"),
    )
    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email=f"metadata-b-{uuid4().hex}@example.test",
        password_hash=hash_password("Integration-Password-Strong-99"),
    )
    tenant_ids = [tenant_a.id, tenant_b.id]
    tenant_a_id, tenant_b_id = tenant_ids
    user_a_id = user_a.id
    user_b_id = user_b.id

    async with sessions() as session:
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all([user_a, user_b])
        await session.commit()

        invalid_creator = DatabaseConnection(
            tenant_id=tenant_a_id,
            created_by=user_b_id,
            name=f"invalid-{uuid4().hex}",
            database_type="postgresql",
            host="8.8.8.8",
            port=5432,
            database_name="customer",
            username="reader",
            encrypted_password="v1.nonce.ciphertext",
        )
        session.add(invalid_creator)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        connection = DatabaseConnection(
            id=uuid4(),
            tenant_id=tenant_a_id,
            created_by=user_a_id,
            name=f"valid-{uuid4().hex}",
            database_type="postgresql",
            host="8.8.8.8",
            port=5432,
            database_name="customer",
            username="reader",
            encrypted_password="v1.nonce.ciphertext",
        )
        session.add(connection)
        await session.commit()
        connection_id = connection.id

        session.add(
            DatabaseSchema(
                tenant_id=tenant_b_id,
                connection_id=connection_id,
                schema_name="invalid",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        schema = DatabaseSchema(
            id=uuid4(),
            tenant_id=tenant_a_id,
            connection_id=connection_id,
            schema_name="business",
        )
        session.add(schema)
        await session.commit()
        schema_id = schema.id
        session.add(
            DatabaseTable(
                tenant_id=tenant_b_id,
                connection_id=connection_id,
                schema_id=schema_id,
                table_name="invalid",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        table = DatabaseTable(
            id=uuid4(),
            tenant_id=tenant_a_id,
            connection_id=connection_id,
            schema_id=schema_id,
            table_name="customers",
        )
        session.add(table)
        await session.commit()
        table_id = table.id
        session.add(
            DatabaseColumn(
                tenant_id=tenant_b_id,
                table_id=table_id,
                column_name="id",
                data_type="bigint",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
        await session.commit()
    await engine.dispose()
