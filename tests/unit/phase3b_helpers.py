"""Phase 3B permission and SQL security fixtures."""

from dataclasses import dataclass
from uuid import uuid4

from models import DatabaseColumn, DatabaseConnection, DatabaseSchema, DatabaseTable
from services.database.permission_resolver import (
    EffectiveColumn,
    EffectiveSchema,
    EffectiveTable,
)
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import SeededIdentity


@dataclass(frozen=True)
class SeededCatalog:
    connection: DatabaseConnection
    schema: DatabaseSchema
    customers: DatabaseTable
    orders: DatabaseTable
    customer_columns: tuple[DatabaseColumn, ...]
    order_columns: tuple[DatabaseColumn, ...]


async def seed_catalog(
    database: DatabaseHarness, identity: SeededIdentity, *, name: str = "customer"
) -> SeededCatalog:
    connection = DatabaseConnection(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        created_by=identity.user.id,
        name=name,
        database_type="postgresql",
        host="8.8.8.8",
        port=5432,
        database_name="customer",
        username="reader",
        encrypted_password="v1.nonce.ciphertext",
        status="connected",
    )
    schema = DatabaseSchema(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        connection_id=connection.id,
        schema_name="business",
    )
    customers = DatabaseTable(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        connection_id=connection.id,
        schema_id=schema.id,
        table_name="customers",
        table_type="table",
    )
    orders = DatabaseTable(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        connection_id=connection.id,
        schema_id=schema.id,
        table_name="orders",
        table_type="table",
    )
    customer_columns = (
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=customers.id,
            column_name="id",
            data_type="bigint",
            ordinal_position=1,
            is_nullable=False,
            is_primary_key=True,
        ),
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=customers.id,
            column_name="country",
            data_type="character varying",
            ordinal_position=2,
            is_nullable=False,
        ),
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=customers.id,
            column_name="tax_identifier",
            data_type="character varying",
            ordinal_position=3,
            is_nullable=True,
            is_sensitive=True,
        ),
    )
    order_columns = (
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=orders.id,
            column_name="id",
            data_type="bigint",
            ordinal_position=1,
            is_nullable=False,
            is_primary_key=True,
        ),
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=orders.id,
            column_name="customer_id",
            data_type="bigint",
            ordinal_position=2,
            is_nullable=False,
            is_foreign_key=True,
            referenced_schema="business",
            referenced_table="customers",
            referenced_column="id",
        ),
        DatabaseColumn(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            table_id=orders.id,
            column_name="total_amount",
            data_type="numeric",
            ordinal_position=3,
            is_nullable=False,
        ),
    )
    async with database.sessions() as session:
        session.add(connection)
        await session.flush()
        session.add(schema)
        await session.flush()
        session.add_all([customers, orders])
        await session.flush()
        session.add_all([*customer_columns, *order_columns])
        await session.commit()
    return SeededCatalog(
        connection, schema, customers, orders, customer_columns, order_columns
    )


def effective_schema(
    *,
    hidden_sensitive: bool = True,
    filter_country: bool = True,
    aggregate_id: bool = True,
    row_filters: tuple[dict[str, object], ...] = (),
) -> EffectiveSchema:
    tenant_id = uuid4()
    connection_id = uuid4()
    schema = DatabaseSchema(
        id=uuid4(),
        tenant_id=tenant_id,
        connection_id=connection_id,
        schema_name="business",
    )
    customers = DatabaseTable(
        id=uuid4(),
        tenant_id=tenant_id,
        connection_id=connection_id,
        schema_id=schema.id,
        table_name="customers",
        table_type="table",
    )
    columns = (
        EffectiveColumn(
            DatabaseColumn(
                id=uuid4(),
                tenant_id=tenant_id,
                table_id=customers.id,
                column_name="id",
                data_type="bigint",
                ordinal_position=1,
                is_nullable=False,
            ),
            True,
            True,
            aggregate_id,
            None,
        ),
        EffectiveColumn(
            DatabaseColumn(
                id=uuid4(),
                tenant_id=tenant_id,
                table_id=customers.id,
                column_name="country",
                data_type="text",
                ordinal_position=2,
                is_nullable=False,
            ),
            True,
            filter_country,
            True,
            None,
        ),
        EffectiveColumn(
            DatabaseColumn(
                id=uuid4(),
                tenant_id=tenant_id,
                table_id=customers.id,
                column_name="tax_identifier",
                data_type="text",
                ordinal_position=3,
                is_nullable=True,
                is_sensitive=True,
            ),
            not hidden_sensitive,
            False,
            False,
            "redact" if not hidden_sensitive else None,
        ),
    )
    return EffectiveSchema(
        connection_id, (EffectiveTable(customers, schema, columns, row_filters),)
    )
