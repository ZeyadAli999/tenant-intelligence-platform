"""Live permission-controlled PostgreSQL execution and bypass resistance."""

from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.exceptions import ResourceNotFoundError
from core.encryption import CredentialCipher, credential_context
from core.security import hash_password
from core.tenant_context import TenantContext
from models import (
    ColumnPermission,
    DatabaseColumn,
    DatabaseConnection,
    QueryExecution,
    Role,
    TablePermission,
    Tenant,
    User,
    UserRole,
)
from repositories.database_connections import DatabaseConnectionRepository
from repositories.permissions import PermissionRepository
from services.database.query_executor import SafeQueryRejectedError, SafeQueryService
from tests.integration.test_customer_postgresql import (
    customer_parameters,
    integration_adapter,
)
from tests.integration.test_migrations import run_alembic

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_live_safe_query_permissions_filters_masking_and_bypasses(
    postgres_test_url: str,
) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    customer = customer_parameters()
    adapter, validator = integration_adapter()
    discovered = await adapter.discover_schema(customer, validator)
    settings = Settings(
        allow_private_database_hosts=True,
        safe_query_max_rows=20,
        customer_database_connect_timeout_seconds=3,
        customer_database_command_timeout_seconds=5,
    )
    tenant = Tenant(id=uuid4(), name="Safe Query Live", code=f"safe-live-{uuid4().hex}")
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email=f"safe-live-{uuid4().hex}@example.com",
        password_hash=hash_password("Integration-Password-Strong-99"),
    )
    role = Role(id=uuid4(), tenant_id=tenant.id, name="egypt-analyst")
    other_tenant = Tenant(
        id=uuid4(), name="Safe Query Other", code=f"safe-other-{uuid4().hex}"
    )
    other_user = User(
        id=uuid4(),
        tenant_id=other_tenant.id,
        email=f"safe-other-{uuid4().hex}@example.com",
        password_hash=hash_password("Integration-Password-Strong-98"),
    )
    connection = DatabaseConnection(
        id=uuid4(),
        tenant_id=tenant.id,
        created_by=user.id,
        name="safe-live-customer",
        database_type="postgresql",
        host=customer.host,
        port=customer.port,
        database_name=customer.database_name,
        username=customer.username,
        encrypted_password="pending",
        status="connected",
    )
    connection.encrypted_password = CredentialCipher.from_settings(settings).encrypt(
        customer.password, associated_data=credential_context(tenant.id, connection.id)
    )
    engine = create_async_engine(postgres_test_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        session.add_all([tenant, other_tenant])
        await session.flush()
        session.add_all([user, role, other_user])
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant.id))
        session.add(connection)
        await session.commit()
        await DatabaseConnectionRepository(session).reconcile_metadata(
            tenant_id=tenant.id, connection_id=connection.id, discovered=discovered
        )
        await session.commit()
        columns = list(
            (
                await session.scalars(
                    select(DatabaseColumn).where(DatabaseColumn.tenant_id == tenant.id)
                )
            ).all()
        )
        country = next(item for item in columns if item.column_name == "country")
        tax = next(item for item in columns if item.column_name == "tax_identifier")
        customer_id = next(
            item
            for item in columns
            if item.column_name == "id" and item.table_id == country.table_id
        )
        tax.is_sensitive = True
        permission = TablePermission(
            id=uuid4(),
            tenant_id=tenant.id,
            role_id=role.id,
            connection_id=connection.id,
            table_id=country.table_id,
            can_read=True,
            can_insert=False,
            can_update=False,
            can_delete=False,
            row_filter={
                "version": 1,
                "all": [
                    {
                        "column_id": str(country.id),
                        "operator": "eq",
                        "value": {"source": "literal", "value": "Egypt"},
                    }
                ],
            },
        )
        session.add(permission)
        await session.flush()
        session.add_all(
            [
                ColumnPermission(
                    tenant_id=tenant.id,
                    table_id=country.table_id,
                    table_permission_id=permission.id,
                    column_id=column.id,
                    can_read=True,
                    can_filter=column.id == country.id,
                    can_aggregate=column.id in (customer_id.id, tax.id),
                    mask_type="redact" if column.id == tax.id else None,
                )
                for column in (customer_id, country, tax)
            ]
        )
        await session.commit()
        context = TenantContext(user, tenant, (role,))
        service = SafeQueryService(session, settings=settings)
        permitted_queries = (
            "SELECT id, country, tax_identifier FROM business.customers",
            "SELECT id, country, tax_identifier FROM business.customers WHERE country = 'France' OR 1 = 1",
            "SELECT c.id, c.country, c.tax_identifier FROM business.customers c",
            "WITH x AS (SELECT id, country, tax_identifier FROM business.customers) SELECT id, country, tax_identifier FROM x",
            "SELECT id, country, tax_identifier FROM (SELECT id, country, tax_identifier FROM business.customers) x",
            "SELECT id, country, tax_identifier FROM business.customers UNION SELECT id, country, tax_identifier FROM business.customers",
        )
        for index, sql in enumerate(permitted_queries):
            result = await service.execute(
                context, connection.id, sql, request_id=f"live-{index}"
            )
            assert result.rows
            assert {row["country"] for row in result.rows} == {"Egypt"}
            assert {row["tax_identifier"] for row in result.rows} == {"***"}
        lineage_queries = {
            "public_value": (
                "SELECT tax_identifier AS public_value FROM business.customers"
            ),
            "hidden_name": (
                "WITH x AS (SELECT tax_identifier AS hidden_name "
                "FROM business.customers) SELECT hidden_name FROM x"
            ),
            "second_name": (
                "WITH x AS (SELECT tax_identifier AS first_name "
                "FROM business.customers), y AS (SELECT first_name AS second_name "
                "FROM x) SELECT second_name FROM y"
            ),
            "renamed_value": (
                "SELECT renamed_value FROM (SELECT tax_identifier AS renamed_value "
                "FROM business.customers) q"
            ),
            "combined": (
                "SELECT combined FROM (SELECT tax_identifier || '-suffix' AS combined "
                "FROM business.customers) q"
            ),
            "exposed": (
                "WITH x AS (SELECT COALESCE(tax_identifier, '') AS exposed "
                "FROM business.customers) SELECT exposed FROM x"
            ),
            "value": (
                "WITH x AS (SELECT tax_identifier AS value FROM business.customers) "
                "SELECT value FROM x UNION ALL SELECT value FROM x"
            ),
            "transformed": (
                "WITH x AS (SELECT CASE WHEN tax_identifier IS NULL THEN '' "
                "ELSE tax_identifier END AS transformed FROM business.customers) "
                "SELECT transformed FROM x"
            ),
            "cast_value": (
                "SELECT CAST(tax_identifier AS TEXT) AS cast_value "
                "FROM business.customers"
            ),
            "lowered": (
                "SELECT LOWER(tax_identifier) AS lowered FROM business.customers"
            ),
            "maximum_tax": (
                "SELECT MAX(tax_identifier) AS maximum_tax FROM business.customers"
            ),
        }
        for index, (output_name, sql) in enumerate(lineage_queries.items()):
            result = await service.execute(
                context, connection.id, sql, request_id=f"live-lineage-{index}"
            )
            assert result.rows
            assert {row[output_name] for row in result.rows} == {"***"}
        ordinary = await service.execute(
            context,
            connection.id,
            "SELECT UPPER(country) AS visible_country FROM business.customers",
            request_id="live-lineage-ordinary",
        )
        assert {row["visible_country"] for row in ordinary.rows} == {"EGYPT"}
        for sql in (
            "SELECT id FROM business.orders",
            "SELECT email FROM business.customers",
            "DELETE FROM business.customers",
        ):
            with pytest.raises(SafeQueryRejectedError):
                await service.execute(
                    context, connection.id, sql, request_id="live-rejected"
                )
        with pytest.raises(SafeQueryRejectedError):
            await service.execute(
                context,
                connection.id,
                "SELECT a.id, b.id FROM business.customers a "
                "JOIN business.customers b ON a.id = b.id",
                request_id="live-duplicate-columns",
            )
        duplicate_record = await session.scalar(
            select(QueryExecution).order_by(QueryExecution.created_at.desc())
        )
        assert duplicate_record is not None
        assert "DUPLICATE_OUTPUT_COLUMN" in {
            item["code"] for item in duplicate_record.validation_errors
        }
        records = list(
            (
                await session.scalars(
                    select(QueryExecution).where(QueryExecution.tenant_id == tenant.id)
                )
            ).all()
        )
        assert len(records) == len(permitted_queries) + len(lineage_queries) + 5
        assert all("EG-SECRET" not in str(record.result_preview) for record in records)
        other_context = TenantContext(other_user, other_tenant, ())
        with pytest.raises(ResourceNotFoundError):
            await service.execute(
                other_context,
                connection.id,
                "SELECT id FROM business.customers",
                request_id="live-cross-tenant",
            )
        assert (
            await DatabaseConnectionRepository(session).get_connection(
                other_tenant.id, connection.id
            )
            is None
        )
        assert (
            await PermissionRepository(session).get_permission(
                other_tenant.id, permission.id
            )
            is None
        )
        assert not list(
            (
                await session.scalars(
                    select(QueryExecution).where(
                        QueryExecution.tenant_id == other_tenant.id
                    )
                )
            ).all()
        )
        await session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await session.execute(delete(Tenant).where(Tenant.id == other_tenant.id))
        await session.commit()
    direct = await asyncpg.connect(
        host=customer.host,
        port=customer.port,
        database=customer.database_name,
        user=customer.username,
        password=customer.password,
    )
    try:
        assert await direct.fetchval("SELECT count(*) FROM business.customers") == 3
    finally:
        await direct.close()
    await engine.dispose()
