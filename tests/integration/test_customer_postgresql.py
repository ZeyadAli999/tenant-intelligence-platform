"""Live PostgreSQL adapter testing and catalog-only discovery."""

import os

import asyncpg
import pytest

from app.config import Settings
from services.database.adapters.base import ConnectionParameters
from services.database.adapters.postgresql import PostgreSQLAdapter
from services.database.host_security import HostSecurityValidator

pytestmark = pytest.mark.integration


def customer_parameters() -> ConnectionParameters:
    required = {
        name: os.environ.get(name)
        for name in (
            "CUSTOMER_TEST_HOST",
            "CUSTOMER_TEST_PORT",
            "CUSTOMER_TEST_DATABASE",
            "CUSTOMER_TEST_USERNAME",
            "CUSTOMER_TEST_PASSWORD",
        )
    }
    if not all(required.values()):
        pytest.skip("Customer PostgreSQL integration settings are not configured")
    return ConnectionParameters(
        host=str(required["CUSTOMER_TEST_HOST"]),
        port=int(str(required["CUSTOMER_TEST_PORT"])),
        database_name=str(required["CUSTOMER_TEST_DATABASE"]),
        username=str(required["CUSTOMER_TEST_USERNAME"]),
        password=str(required["CUSTOMER_TEST_PASSWORD"]),
        ssl_enabled=False,
        ssl_settings={},
        connection_options={"application_name": "phase3a-integration"},
    )


def integration_adapter() -> tuple[PostgreSQLAdapter, HostSecurityValidator]:
    settings = Settings(
        allow_private_database_hosts=True,
        customer_database_connect_timeout_seconds=3,
        customer_database_command_timeout_seconds=5,
    )
    return PostgreSQLAdapter(settings=settings), HostSecurityValidator(
        allow_private=True
    )


@pytest.mark.asyncio
async def test_customer_postgresql_connection_and_schema_discovery() -> None:
    parameters = customer_parameters()
    adapter, validator = integration_adapter()

    tested = await adapter.test_connection(parameters, validator)
    discovered = await adapter.discover_schema(parameters, validator)

    assert tested.success is True
    schema_names = {schema.name for schema in discovered}
    assert "business" in schema_names
    assert not {"pg_catalog", "information_schema", "pg_toast"} & schema_names
    business = next(schema for schema in discovered if schema.name == "business")
    tables = {table.name: table for table in business.tables}
    assert {"customers", "orders", "invoices", "customer_order_totals"}.issubset(tables)
    assert tables["customer_order_totals"].table_type == "view"
    assert tables["customers"].primary_key_columns == ("id",)
    order_columns = {column.name: column for column in tables["orders"].columns}
    assert order_columns["customer_id"].is_foreign_key is True
    assert order_columns["customer_id"].referenced_table == "customers"
    assert all(
        not hasattr(column, "sample_values") for column in order_columns.values()
    )


@pytest.mark.asyncio
async def test_customer_postgresql_failures_are_safely_categorized() -> None:
    parameters = customer_parameters()
    adapter, validator = integration_adapter()

    wrong_password = ConnectionParameters(
        **{**parameters.__dict__, "password": "definitely-wrong-password"}
    )
    missing_database = ConnectionParameters(
        **{**parameters.__dict__, "database_name": "missing_phase3a_database"}
    )
    authentication_result = await adapter.test_connection(wrong_password, validator)
    missing_result = await adapter.test_connection(missing_database, validator)

    assert authentication_result.success is False
    assert authentication_result.error_code == "AUTHENTICATION_FAILED"
    assert "definitely-wrong-password" not in authentication_result.message
    assert missing_result.success is False
    assert missing_result.error_code == "DATABASE_NOT_FOUND"


@pytest.mark.asyncio
async def test_customer_reader_is_genuinely_read_only() -> None:
    parameters = customer_parameters()
    connection = await asyncpg.connect(
        host=parameters.host,
        port=parameters.port,
        database=parameters.database_name,
        user=parameters.username,
        password=parameters.password,
        timeout=3,
    )
    try:
        assert await connection.fetchval("SELECT 1") == 1
        initial_counts = (
            await connection.fetchval("SELECT count(*) FROM business.customers"),
            await connection.fetchval("SELECT count(*) FROM business.orders"),
            await connection.fetchval("SELECT count(*) FROM business.invoices"),
        )
        role = await connection.fetchrow(
            """SELECT rolsuper, rolcreatedb, rolcreaterole
            FROM pg_roles WHERE rolname = current_user"""
        )
        assert role is not None
        assert tuple(role) == (False, False, False)
        assert (
            await connection.fetchval(
                """SELECT pg_get_userbyid(datdba) = current_user
            FROM pg_database WHERE datname = current_database()"""
            )
            is False
        )

        forbidden_statements = (
            "INSERT INTO business.customers (customer_code, name) VALUES ('DENIED', 'Denied')",
            "UPDATE business.customers SET name = 'Denied' WHERE customer_code = 'CUST-001'",
            "DELETE FROM business.customers WHERE customer_code = 'CUST-002'",
            "CREATE TABLE business.reader_forbidden (id bigint)",
            "CREATE TEMP TABLE reader_temp_forbidden (id bigint)",
            "DROP TABLE business.customers",
        )
        for statement in forbidden_statements:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with connection.transaction():
                    await connection.execute(statement)

        final_counts = (
            await connection.fetchval("SELECT count(*) FROM business.customers"),
            await connection.fetchval("SELECT count(*) FROM business.orders"),
            await connection.fetchval("SELECT count(*) FROM business.invoices"),
        )
        assert final_counts == initial_counts
        assert (
            await connection.fetchval(
                """SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'business' AND table_name = 'reader_forbidden'"""
            )
            == 0
        )
    finally:
        await connection.close()
