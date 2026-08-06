"""Controlled execution, masking, audit, failure, and pre-database rejection tests."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import Settings
from core.encryption import CredentialCipher, credential_context
from core.tenant_context import TenantContext
from models import ColumnPermission, QueryExecution, TablePermission
from services.database.adapters.base import (
    AdapterQueryResult,
    AdapterTestResult,
    ConnectionParameters,
    DatabaseAdapter,
    DiscoveredSchema,
    QueryLimits,
)
from services.database.dialect_resolver import AdapterRegistry
from services.database.host_security import HostSecurityValidator
from services.database.query_executor import SafeQueryRejectedError, SafeQueryService
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity
from tests.unit.phase3b_helpers import seed_catalog


class FakeExecutionAdapter(DatabaseAdapter):
    database_type = "postgresql"

    def __init__(
        self,
        failure: Exception | None = None,
        *,
        columns: tuple[str, ...] = ("id", "country", "tax_identifier"),
        rows: tuple[dict[str, object], ...] = (
            {"id": 1, "country": "Egypt", "tax_identifier": "EG-SECRET-001"},
        ),
    ) -> None:
        self.failure = failure
        self.columns = columns
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object], QueryLimits]] = []

    async def test_connection(
        self, parameters: ConnectionParameters, host_validator: HostSecurityValidator
    ) -> AdapterTestResult:
        return AdapterTestResult(True, None, "ok")

    async def discover_schema(
        self, parameters: ConnectionParameters, host_validator: HostSecurityValidator
    ) -> tuple[DiscoveredSchema, ...]:
        return ()

    async def execute_query(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
        sql: str,
        bound_parameters: dict[str, object],
        limits: QueryLimits,
    ) -> AdapterQueryResult:
        self.calls.append((sql, bound_parameters, limits))
        if self.failure:
            raise self.failure
        return AdapterQueryResult(
            columns=self.columns,
            rows=self.rows,
            truncated=False,
        )


async def setup_execution(
    database: DatabaseHarness, settings: Settings
) -> tuple[object, object, TenantContext]:
    identity = await seed_identity(database)
    catalog = await seed_catalog(database, identity)
    cipher = CredentialCipher.from_settings(settings)
    async with database.sessions() as session:
        connection = await session.get(type(catalog.connection), catalog.connection.id)
        assert connection is not None
        connection.encrypted_password = cipher.encrypt(
            "customer-password",
            associated_data=credential_context(identity.tenant.id, connection.id),
        )
        permission = TablePermission(
            id=uuid4(),
            tenant_id=identity.tenant.id,
            role_id=identity.roles[0].id,
            connection_id=connection.id,
            table_id=catalog.customers.id,
            can_read=True,
            can_insert=False,
            can_update=False,
            can_delete=False,
            row_filter={
                "version": 1,
                "all": [
                    {
                        "column_id": str(catalog.customer_columns[1].id),
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
                    tenant_id=identity.tenant.id,
                    table_id=catalog.customers.id,
                    table_permission_id=permission.id,
                    column_id=column.id,
                    can_read=True,
                    can_filter=column.column_name == "country",
                    can_aggregate=column.column_name == "id",
                    mask_type="redact"
                    if column.column_name == "tax_identifier"
                    else None,
                )
                for column in catalog.customer_columns
            ]
        )
        await session.commit()
    return (
        identity,
        catalog,
        TenantContext(identity.user, identity.tenant, identity.roles),
    )


@pytest.mark.asyncio
async def test_safe_query_masks_before_return_and_audit_and_injects_filter(
    test_database: DatabaseHarness,
) -> None:
    settings = Settings()
    identity, catalog, context = await setup_execution(test_database, settings)
    adapter = FakeExecutionAdapter()
    async with test_database.sessions() as session:
        result = await SafeQueryService(
            session, settings=settings, registry=AdapterRegistry((adapter,))
        ).execute(
            context,
            catalog.connection.id,
            "SELECT id, country, tax_identifier FROM business.customers WHERE country = 'France' OR 1 = 1",
            request_id="safe-query-test",
        )
        record = await session.get(QueryExecution, result.query_execution_id)
    assert result.rows[0]["tax_identifier"] == "***"
    assert adapter.calls and "Egypt" not in adapter.calls[0][0]
    assert set(adapter.calls[0][1].values()) == {"Egypt"}
    assert record is not None
    assert record.execution_status == "succeeded"
    assert record.result_preview[0]["tax_identifier"] == "***"
    assert "France" not in record.generated_sql
    assert "EG-SECRET-001" not in str(record.result_preview)
    assert identity.tenant.id == record.tenant_id


@pytest.mark.asyncio
async def test_safe_query_masks_renamed_cte_output_before_return_audit_and_logs(
    test_database: DatabaseHarness, caplog: pytest.LogCaptureFixture
) -> None:
    settings = Settings()
    _, catalog, context = await setup_execution(test_database, settings)
    adapter = FakeExecutionAdapter(
        columns=("leaked_value",),
        rows=({"leaked_value": "EG-SECRET-001"},),
    )
    async with test_database.sessions() as session:
        result = await SafeQueryService(
            session, settings=settings, registry=AdapterRegistry((adapter,))
        ).execute(
            context,
            catalog.connection.id,
            "WITH x AS (SELECT tax_identifier AS leaked_value "
            "FROM business.customers) SELECT leaked_value FROM x",
            request_id="lineage-mask-test",
        )
        record = await session.get(QueryExecution, result.query_execution_id)
    assert result.rows == ({"leaked_value": "***"},)
    assert record is not None and record.result_preview == [{"leaked_value": "***"}]
    assert "EG-SECRET-001" not in caplog.text
    assert "EG-SECRET-001" not in str(record.result_preview)


@pytest.mark.asyncio
async def test_destructive_sql_is_rejected_before_adapter_call_and_audited(
    test_database: DatabaseHarness,
) -> None:
    settings = Settings()
    _, catalog, context = await setup_execution(test_database, settings)
    adapter = FakeExecutionAdapter()
    async with test_database.sessions() as session:
        with pytest.raises(SafeQueryRejectedError):
            await SafeQueryService(
                session, settings=settings, registry=AdapterRegistry((adapter,))
            ).execute(
                context,
                catalog.connection.id,
                "DELETE FROM business.customers",
                request_id="rejected",
            )
        record = await session.scalar(
            select(QueryExecution).order_by(QueryExecution.created_at.desc())
        )
    assert adapter.calls == []
    assert record is not None and record.execution_status == "rejected"
    assert record.validation_errors


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [RuntimeError("driver detail secret"), asyncio.TimeoutError()]
)
async def test_execution_failures_are_sanitized_and_audited(
    test_database: DatabaseHarness, failure: Exception
) -> None:
    settings = Settings()
    _, catalog, context = await setup_execution(test_database, settings)
    adapter = FakeExecutionAdapter(failure)
    async with test_database.sessions() as session:
        with pytest.raises(SafeQueryRejectedError):
            await SafeQueryService(
                session, settings=settings, registry=AdapterRegistry((adapter,))
            ).execute(
                context,
                catalog.connection.id,
                "SELECT id FROM business.customers",
                request_id="failed",
            )
        record = await session.scalar(
            select(QueryExecution).order_by(QueryExecution.created_at.desc())
        )
    assert record is not None
    assert record.execution_status in ("failed", "timeout")
    assert "driver detail secret" not in (record.error_message or "")
