"""Identity-stable metadata reconciliation and transactional rollback tests."""

from uuid import UUID

import pytest
from sqlalchemy import select

from models import DatabaseColumn, DatabaseConnection, DatabaseSchema, DatabaseTable
from repositories.database_connections import DatabaseConnectionRepository
from services.database.adapters.base import (
    DiscoveredColumn,
    DiscoveredSchema,
    DiscoveredTable,
)
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import SeededIdentity, seed_identity


def column(
    name: str,
    *,
    data_type: str = "bigint",
    description: str | None = None,
    ordinal: int = 1,
) -> DiscoveredColumn:
    return DiscoveredColumn(
        name=name,
        data_type=data_type,
        ordinal_position=ordinal,
        is_nullable=False,
        is_primary_key=name == "id",
        description=description,
    )


def table(
    name: str,
    *columns: DiscoveredColumn,
    description: str | None = None,
) -> DiscoveredTable:
    return DiscoveredTable(
        schema_name="business",
        name=name,
        table_type="table",
        estimated_row_count=2,
        primary_key_columns=("id",)
        if any(item.name == "id" for item in columns)
        else (),
        description=description,
        columns=columns,
    )


def metadata(*tables: DiscoveredTable) -> tuple[DiscoveredSchema, ...]:
    return (DiscoveredSchema(name="business", tables=tables),)


async def add_connection(
    test_database: DatabaseHarness,
    identity: SeededIdentity,
    *,
    name: str = "customer",
) -> UUID:
    async with test_database.sessions() as session:
        connection = DatabaseConnection(
            tenant_id=identity.tenant.id,
            created_by=identity.user.id,
            name=name,
            database_type="postgresql",
            host="8.8.8.8",
            port=5432,
            database_name="customer",
            username="reader",
            encrypted_password="v1.nonce.ciphertext",
        )
        session.add(connection)
        await session.commit()
        return connection.id


async def identities(
    test_database: DatabaseHarness,
    tenant_id: UUID,
    connection_id: UUID,
) -> tuple[dict[str, UUID], dict[str, UUID], dict[tuple[str, str], UUID]]:
    async with test_database.sessions() as session:
        schemas = list(
            (
                await session.scalars(
                    select(DatabaseSchema).where(
                        DatabaseSchema.tenant_id == tenant_id,
                        DatabaseSchema.connection_id == connection_id,
                    )
                )
            ).all()
        )
        tables = list(
            (
                await session.scalars(
                    select(DatabaseTable).where(
                        DatabaseTable.tenant_id == tenant_id,
                        DatabaseTable.connection_id == connection_id,
                    )
                )
            ).all()
        )
        columns = list(
            (
                await session.scalars(
                    select(DatabaseColumn).where(DatabaseColumn.tenant_id == tenant_id)
                )
            ).all()
        )
    table_names = {table.id: table.table_name for table in tables}
    return (
        {schema.schema_name: schema.id for schema in schemas},
        {table.table_name: table.id for table in tables},
        {
            (table_names[item.table_id], item.column_name): item.id
            for item in columns
            if item.table_id in table_names
        },
    )


@pytest.mark.asyncio
async def test_identical_reconciliation_preserves_every_identity(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    connection_id = await add_connection(test_database, identity)
    discovered = metadata(
        table("customers", column("id"), column("name", data_type="varchar", ordinal=2))
    )
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=discovered,
        )
        await session.commit()
    before = await identities(test_database, identity.tenant.id, connection_id)
    async with test_database.sessions() as session:
        await DatabaseConnectionRepository(session).reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=discovered,
        )
        await session.commit()
    assert await identities(test_database, identity.tenant.id, connection_id) == before


@pytest.mark.asyncio
async def test_new_table_and_mutable_column_update_preserve_existing_ids(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    connection_id = await add_connection(test_database, identity)
    initial = metadata(
        table("customers", column("id"), column("name", data_type="varchar", ordinal=2))
    )
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=initial,
        )
        await session.commit()
    before = await identities(test_database, identity.tenant.id, connection_id)
    changed = metadata(
        table(
            "customers",
            column("id"),
            column("name", data_type="text", description="Updated", ordinal=2),
        ),
        table("orders", column("id")),
    )
    async with test_database.sessions() as session:
        await DatabaseConnectionRepository(session).reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=changed,
        )
        await session.commit()
        name_column = await session.scalar(
            select(DatabaseColumn)
            .join(DatabaseTable, DatabaseTable.id == DatabaseColumn.table_id)
            .where(
                DatabaseTable.connection_id == connection_id,
                DatabaseColumn.column_name == "name",
            )
        )
    after = await identities(test_database, identity.tenant.id, connection_id)
    assert after[0]["business"] == before[0]["business"]
    assert after[1]["customers"] == before[1]["customers"]
    assert after[2][("customers", "id")] == before[2][("customers", "id")]
    assert after[2][("customers", "name")] == before[2][("customers", "name")]
    assert "orders" not in before[1] and "orders" in after[1]
    assert name_column is not None
    assert (name_column.data_type, name_column.description) == ("text", "Updated")


@pytest.mark.asyncio
async def test_stale_table_is_disabled_then_restored_with_same_identity(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    connection_id = await add_connection(test_database, identity)
    discovered = metadata(
        table("customers", column("id")), table("orders", column("id"))
    )
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=discovered,
        )
        await session.commit()
    before = await identities(test_database, identity.tenant.id, connection_id)
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=metadata(table("customers", column("id"))),
        )
        await session.commit()
        stale = await session.scalar(
            select(DatabaseTable).where(DatabaseTable.id == before[1]["orders"])
        )
        assert stale is not None and stale.is_enabled is False
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=discovered,
        )
        await session.commit()
        restored = await session.scalar(
            select(DatabaseTable).where(DatabaseTable.id == before[1]["orders"])
        )
    assert restored is not None and restored.is_enabled is True
    assert (await identities(test_database, identity.tenant.id, connection_id))[1][
        "orders"
    ] == before[1]["orders"]


@pytest.mark.asyncio
async def test_removed_column_does_not_recreate_remaining_columns(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    connection_id = await add_connection(test_database, identity)
    initial = metadata(
        table(
            "customers",
            column("id"),
            column("name", data_type="text", ordinal=2),
            column("email", data_type="text", ordinal=3),
        )
    )
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=initial,
        )
        await session.commit()
    before = await identities(test_database, identity.tenant.id, connection_id)
    async with test_database.sessions() as session:
        await DatabaseConnectionRepository(session).reconcile_metadata(
            tenant_id=identity.tenant.id,
            connection_id=connection_id,
            discovered=metadata(
                table(
                    "customers",
                    column("id"),
                    column("name", data_type="text", ordinal=2),
                )
            ),
        )
        await session.commit()
    after = await identities(test_database, identity.tenant.id, connection_id)
    assert after[2][("customers", "id")] == before[2][("customers", "id")]
    assert after[2][("customers", "name")] == before[2][("customers", "name")]
    assert ("customers", "email") not in after[2]


@pytest.mark.asyncio
async def test_reconciliation_is_tenant_scoped_and_failure_rolls_back_all_changes(
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(
        test_database, tenant_code="cache-a", email="cache@example.com"
    )
    tenant_b = await seed_identity(
        test_database, tenant_code="cache-b", email="cache@example.com"
    )
    connection_a = await add_connection(test_database, tenant_a, name="customer-a")
    connection_b = await add_connection(test_database, tenant_b, name="customer-b")
    initial = metadata(table("customers", column("id")))
    async with test_database.sessions() as session:
        repository = DatabaseConnectionRepository(session)
        await repository.reconcile_metadata(
            tenant_id=tenant_a.tenant.id, connection_id=connection_a, discovered=initial
        )
        await repository.reconcile_metadata(
            tenant_id=tenant_b.tenant.id, connection_id=connection_b, discovered=initial
        )
        await session.commit()
    tenant_b_before = await identities(test_database, tenant_b.tenant.id, connection_b)
    tenant_a_before = await identities(test_database, tenant_a.tenant.id, connection_a)
    async with test_database.sessions() as session:
        try:
            await DatabaseConnectionRepository(session).reconcile_metadata(
                tenant_id=tenant_a.tenant.id,
                connection_id=connection_a,
                discovered=metadata(
                    table("customers", column("id", data_type="uuid")),
                    table("orders", column("id")),
                ),
            )
            raise RuntimeError("simulated cache failure")
        except RuntimeError:
            await session.rollback()
    assert (
        await identities(test_database, tenant_a.tenant.id, connection_a)
        == tenant_a_before
    )
    assert (
        await identities(test_database, tenant_b.tenant.id, connection_b)
        == tenant_b_before
    )
