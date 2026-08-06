"""Connection testing and schema-sync orchestration tests with injected adapters."""

from unittest.mock import patch

import pytest

from app.config import Settings
from core.encryption import CredentialCipher
from schemas.database_connections import DatabaseConnectionCreateRequest
from services.database.adapters.base import (
    AdapterTestResult,
    ConnectionParameters,
    DatabaseAdapter,
    DiscoveredColumn,
    DiscoveredSchema,
    DiscoveredTable,
)
from services.database.connection_service import DatabaseConnectionService
from services.database.dialect_resolver import AdapterRegistry
from services.database.host_security import HostSecurityValidator
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity


class FakePostgreSQLAdapter(DatabaseAdapter):
    database_type = "postgresql"

    def __init__(self) -> None:
        self.fail_discovery = False
        self.test_result = AdapterTestResult(True, None, "Connection succeeded")

    async def test_connection(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> AdapterTestResult:
        await host_validator.resolve_and_validate(parameters.host, parameters.port)
        return self.test_result

    async def discover_schema(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> tuple[DiscoveredSchema, ...]:
        await host_validator.resolve_and_validate(parameters.host, parameters.port)
        if self.fail_discovery:
            raise RuntimeError("password=must-not-be-logged")
        return (
            DiscoveredSchema(
                name="business",
                tables=(
                    DiscoveredTable(
                        schema_name="business",
                        name="customers",
                        table_type="table",
                        estimated_row_count=2,
                        primary_key_columns=("id",),
                        columns=(
                            DiscoveredColumn(
                                name="id",
                                data_type="bigint",
                                ordinal_position=1,
                                is_nullable=False,
                                is_primary_key=True,
                            ),
                        ),
                    ),
                ),
            ),
        )


async def public_resolver(_: str, __: int) -> tuple[str, ...]:
    return ("8.8.8.8",)


def service_settings() -> Settings:
    return Settings(
        connection_encryption_key=("AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")
    )


def create_payload() -> DatabaseConnectionCreateRequest:
    return DatabaseConnectionCreateRequest(
        name="customer",
        database_type="postgresql",
        host="database.example.com",
        port=5432,
        database_name="customer",
        username="reader",
        password="customer-password",
    )


@pytest.mark.asyncio
async def test_test_and_sync_update_status_and_cache_transactionally(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    adapter = FakePostgreSQLAdapter()
    settings = service_settings()
    validator = HostSecurityValidator(
        allow_private=False,
        resolver=public_resolver,
    )
    async with test_database.sessions() as session:
        service = DatabaseConnectionService(
            session,
            identity.tenant.id,
            settings=settings,
            registry=AdapterRegistry((adapter,)),
            host_validator=validator,
            cipher=CredentialCipher.from_settings(settings),
        )
        created = await service.create(create_payload(), created_by=identity.user.id)
        tested = await service.test_connection(created.id, request_id="service-test-1")
        synced = await service.sync_schema(created.id, request_id="service-sync-1")
        schemas = await service.list_schemas(created.id, page=1, page_size=50)
        tables = await service.list_tables(
            created.id,
            page=1,
            page_size=50,
            schema_name=None,
            enabled=True,
            table_type="table",
            search="customer",
        )

        assert tested.success is True
        assert tested.status == "connected"
        assert synced.success is True
        assert (synced.schema_count, synced.table_count, synced.column_count) == (
            1,
            1,
            1,
        )
        assert schemas.total == 1
        assert tables.total == 1
        assert tables.items[0].columns[0].is_primary_key is True

        adapter.fail_discovery = True
        with patch("services.database.connection_service.logger.warning") as sync_log:
            failed = await service.sync_schema(
                created.id,
                request_id="service-sync-failed",
            )
        preserved = await service.list_tables(
            created.id,
            page=1,
            page_size=50,
            schema_name=None,
            enabled=None,
            table_type=None,
            search=None,
        )

    assert failed.success is False
    assert failed.message == "Schema synchronization failed"
    assert preserved.total == 1
    logged = repr(sync_log.call_args)
    assert "service-sync-failed" in logged
    assert "must-not-be-logged" not in logged
    assert "password" not in logged.casefold()
