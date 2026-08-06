"""Fast database-level tenant consistency and uniqueness checks."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from models import (
    DatabaseColumn,
    DatabaseConnection,
    DatabaseSchema,
    DatabaseTable,
)
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity


def connection_for(
    tenant_id: object, created_by: object, name: str
) -> DatabaseConnection:
    return DatabaseConnection(
        id=uuid4(),
        tenant_id=tenant_id,
        created_by=created_by,
        name=name,
        database_type="postgresql",
        host="8.8.8.8",
        port=5432,
        database_name="customer",
        username="reader",
        encrypted_password="v1.nonce.ciphertext",
    )


@pytest.mark.asyncio
async def test_cross_tenant_creator_is_rejected(
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        email="admin@globex.example",
    )
    async with test_database.sessions() as session:
        session.add(
            connection_for(tenant_a.tenant.id, tenant_b.user.id, "invalid-creator")
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_cross_tenant_metadata_relationships_are_rejected(
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        email="admin@globex.example",
    )
    connection = connection_for(tenant_a.tenant.id, tenant_a.user.id, "customer")
    connection_id = connection.id
    tenant_a_id = tenant_a.tenant.id
    tenant_b_id = tenant_b.tenant.id
    async with test_database.sessions() as session:
        session.add(connection)
        await session.commit()

        invalid_schema = DatabaseSchema(
            id=uuid4(),
            tenant_id=tenant_b_id,
            connection_id=connection_id,
            schema_name="business",
        )
        session.add(invalid_schema)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        valid_schema = DatabaseSchema(
            id=uuid4(),
            tenant_id=tenant_a_id,
            connection_id=connection_id,
            schema_name="business",
        )
        session.add(valid_schema)
        await session.commit()
        valid_schema_id = valid_schema.id
        invalid_table = DatabaseTable(
            id=uuid4(),
            tenant_id=tenant_b_id,
            connection_id=connection_id,
            schema_id=valid_schema_id,
            table_name="customers",
        )
        session.add(invalid_table)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        valid_table = DatabaseTable(
            id=uuid4(),
            tenant_id=tenant_a_id,
            connection_id=connection_id,
            schema_id=valid_schema_id,
            table_name="customers",
        )
        session.add(valid_table)
        await session.commit()
        valid_table_id = valid_table.id
        session.add(
            DatabaseColumn(
                tenant_id=tenant_b_id,
                table_id=valid_table_id,
                column_name="id",
                data_type="bigint",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
