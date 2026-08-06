"""PostgreSQL runtime connection testing and catalog-only schema discovery."""

import asyncio
import ssl
from collections.abc import Callable

import asyncpg
from sqlalchemy import URL, text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings
from services.database.adapters.base import (
    AdapterQueryResult,
    AdapterTestResult,
    ConnectionParameters,
    DatabaseAdapter,
    DiscoveredColumn,
    DiscoveredSchema,
    DiscoveredTable,
    QueryLimits,
)
from services.database.host_security import HostSecurityError, HostSecurityValidator

EngineFactory = Callable[[URL, dict[str, object]], AsyncEngine]

_TABLES_QUERY = text(
    """
    SELECT
        n.nspname AS schema_name,
        c.relname AS table_name,
        CASE WHEN c.relkind IN ('v', 'm') THEN 'view' ELSE 'table' END AS table_type,
        CASE WHEN c.reltuples < 0 THEN NULL ELSE c.reltuples::bigint END AS estimated_row_count,
        obj_description(c.oid, 'pg_class') AS description
    FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p', 'v', 'm')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND n.nspname NOT LIKE 'pg_toast_temp_%'
    ORDER BY n.nspname, c.relname
    """
)

_COLUMNS_QUERY = text(
    """
    SELECT
        cols.table_schema AS schema_name,
        cols.table_name,
        cols.column_name,
        CASE
            WHEN cols.data_type = 'USER-DEFINED' THEN cols.udt_name
            ELSE cols.data_type
        END AS data_type,
        cols.ordinal_position,
        cols.is_nullable = 'YES' AS is_nullable,
        pg_catalog.col_description(cls.oid, attrs.attnum) AS description
    FROM information_schema.columns AS cols
    JOIN pg_catalog.pg_namespace AS ns ON ns.nspname = cols.table_schema
    JOIN pg_catalog.pg_class AS cls
      ON cls.relnamespace = ns.oid AND cls.relname = cols.table_name
    JOIN pg_catalog.pg_attribute AS attrs
      ON attrs.attrelid = cls.oid AND attrs.attname = cols.column_name
    WHERE cols.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND cols.table_schema NOT LIKE 'pg_temp_%'
      AND cols.table_schema NOT LIKE 'pg_toast_temp_%'
    ORDER BY cols.table_schema, cols.table_name, cols.ordinal_position
    """
)

_PRIMARY_KEYS_QUERY = text(
    """
    SELECT
        ns.nspname AS table_schema,
        rel.relname AS table_name,
        attr.attname AS column_name
    FROM pg_catalog.pg_constraint AS con
    JOIN pg_catalog.pg_class AS rel ON rel.oid = con.conrelid
    JOIN pg_catalog.pg_namespace AS ns ON ns.oid = rel.relnamespace
    JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS keys(attnum, position)
      ON TRUE
    JOIN pg_catalog.pg_attribute AS attr
      ON attr.attrelid = rel.oid AND attr.attnum = keys.attnum
    WHERE con.contype = 'p'
      AND ns.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND ns.nspname NOT LIKE 'pg_temp_%'
      AND ns.nspname NOT LIKE 'pg_toast_temp_%'
    ORDER BY ns.nspname, rel.relname, keys.position
    """
)

_FOREIGN_KEYS_QUERY = text(
    """
    SELECT
        src_ns.nspname AS table_schema,
        src.relname AS table_name,
        src_col.attname AS column_name,
        dst_ns.nspname AS referenced_schema,
        dst.relname AS referenced_table,
        dst_col.attname AS referenced_column
    FROM pg_catalog.pg_constraint AS con
    JOIN pg_catalog.pg_class AS src ON src.oid = con.conrelid
    JOIN pg_catalog.pg_namespace AS src_ns ON src_ns.oid = src.relnamespace
    JOIN pg_catalog.pg_class AS dst ON dst.oid = con.confrelid
    JOIN pg_catalog.pg_namespace AS dst_ns ON dst_ns.oid = dst.relnamespace
    JOIN LATERAL unnest(con.conkey, con.confkey) AS keys(src_attnum, dst_attnum)
      ON TRUE
    JOIN pg_catalog.pg_attribute AS src_col
      ON src_col.attrelid = src.oid AND src_col.attnum = keys.src_attnum
    JOIN pg_catalog.pg_attribute AS dst_col
      ON dst_col.attrelid = dst.oid AND dst_col.attnum = keys.dst_attnum
    WHERE con.contype = 'f'
      AND src_ns.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    ORDER BY src_ns.nspname, src.relname, src_col.attnum
    """
)


def _default_engine_factory(url: URL, options: dict[str, object]) -> AsyncEngine:
    return create_async_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        echo=False,
        connect_args=options,
    )


class PostgreSQLAdapter(DatabaseAdapter):
    database_type = "postgresql"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        engine_factory: EngineFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.engine_factory = engine_factory or _default_engine_factory

    def _build_engine(self, parameters: ConnectionParameters) -> AsyncEngine:
        url = URL.create(
            "postgresql+asyncpg",
            username=parameters.username,
            password=parameters.password,
            host=parameters.host,
            port=parameters.port,
            database=parameters.database_name,
        )
        ssl_mode: str | bool = False
        if parameters.ssl_enabled:
            ssl_mode = str(parameters.ssl_settings.get("mode", "verify-full"))
        server_settings = {
            "statement_timeout": str(
                int(self.settings.customer_database_command_timeout_seconds * 1000)
            ),
            "default_transaction_read_only": "on",
            "application_name": str(
                parameters.connection_options.get(
                    "application_name",
                    "text-to-sql-schema-discovery",
                )
            ),
        }
        return self.engine_factory(
            url,
            {
                "timeout": self.settings.customer_database_connect_timeout_seconds,
                "command_timeout": self.settings.customer_database_command_timeout_seconds,
                "statement_cache_size": 0,
                "ssl": ssl_mode,
                "server_settings": server_settings,
            },
        )

    async def test_connection(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> AdapterTestResult:
        try:
            await host_validator.resolve_and_validate(parameters.host, parameters.port)
        except HostSecurityError:
            return AdapterTestResult(
                False, "HOST_BLOCKED", "Database host is not allowed"
            )
        engine = self._build_engine(parameters)
        try:
            async with asyncio.timeout(
                self.settings.customer_database_connect_timeout_seconds
                + self.settings.customer_database_command_timeout_seconds
            ):
                async with engine.connect() as connection:
                    await connection.execute(text("SET TRANSACTION READ ONLY"))
                    await connection.execute(text("SELECT 1"))
            return AdapterTestResult(True, None, "Connection succeeded")
        except Exception as exc:  # noqa: BLE001 - categorized without exposing detail
            code, message = self._categorize_error(exc)
            return AdapterTestResult(False, code, message)
        finally:
            await engine.dispose()

    async def discover_schema(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> tuple[DiscoveredSchema, ...]:
        await host_validator.resolve_and_validate(parameters.host, parameters.port)
        engine = self._build_engine(parameters)
        try:
            async with asyncio.timeout(
                self.settings.customer_database_connect_timeout_seconds
                + self.settings.customer_database_command_timeout_seconds * 4
            ):
                async with engine.connect() as connection:
                    await connection.execute(text("SET TRANSACTION READ ONLY"))
                    table_rows = (
                        (await connection.execute(_TABLES_QUERY)).mappings().all()
                    )
                    column_rows = (
                        (await connection.execute(_COLUMNS_QUERY)).mappings().all()
                    )
                    primary_rows = (
                        (await connection.execute(_PRIMARY_KEYS_QUERY)).mappings().all()
                    )
                    foreign_rows = (
                        (await connection.execute(_FOREIGN_KEYS_QUERY)).mappings().all()
                    )
            return self._assemble_metadata(
                table_rows,
                column_rows,
                primary_rows,
                foreign_rows,
            )
        finally:
            await engine.dispose()

    async def execute_query(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
        sql: str,
        bound_parameters: dict[str, object],
        limits: QueryLimits,
    ) -> AdapterQueryResult:
        await host_validator.resolve_and_validate(parameters.host, parameters.port)
        engine = self._build_engine(parameters)
        try:
            async with asyncio.timeout(
                self.settings.customer_database_connect_timeout_seconds
                + limits.statement_timeout_ms / 1000
                + 1
            ):
                async with engine.connect() as connection:
                    async with connection.begin():
                        await connection.execute(text("SET TRANSACTION READ ONLY"))
                        await connection.execute(
                            text(
                                "SELECT set_config('statement_timeout', :value, true)"
                            ),
                            {"value": str(limits.statement_timeout_ms)},
                        )
                        await connection.execute(
                            text("SELECT set_config('lock_timeout', :value, true)"),
                            {"value": str(limits.lock_timeout_ms)},
                        )
                        result = await connection.execute(text(sql), bound_parameters)
                        columns = tuple(result.keys())
                        if len(columns) > limits.max_columns:
                            raise ValueError("Result column limit exceeded")
                        if len(columns) != len(set(columns)):
                            raise ValueError("Duplicate result columns are not allowed")
                        raw_rows = result.mappings().fetchmany(limits.max_rows + 1)
                        truncated = len(raw_rows) > limits.max_rows
                        rows = tuple(dict(row) for row in raw_rows[: limits.max_rows])
            return AdapterQueryResult(columns=columns, rows=rows, truncated=truncated)
        finally:
            await engine.dispose()

    @staticmethod
    def _assemble_metadata(
        table_rows: list[object],
        column_rows: list[object],
        primary_rows: list[object],
        foreign_rows: list[object],
    ) -> tuple[DiscoveredSchema, ...]:
        primary_keys: dict[tuple[str, str], list[str]] = {}
        for row in primary_rows:
            mapping = row  # type: ignore[assignment]
            primary_keys.setdefault(
                (mapping["table_schema"], mapping["table_name"]),
                [],
            ).append(mapping["column_name"])
        foreign_keys = {
            (row["table_schema"], row["table_name"], row["column_name"]): row
            for row in foreign_rows  # type: ignore[index]
        }
        columns_by_table: dict[tuple[str, str], list[DiscoveredColumn]] = {}
        for row in column_rows:
            mapping = row  # type: ignore[assignment]
            key = (mapping["schema_name"], mapping["table_name"])
            foreign = foreign_keys.get((*key, mapping["column_name"]))
            columns_by_table.setdefault(key, []).append(
                DiscoveredColumn(
                    name=mapping["column_name"],
                    data_type=mapping["data_type"],
                    ordinal_position=mapping["ordinal_position"],
                    is_nullable=mapping["is_nullable"],
                    is_primary_key=mapping["column_name"] in primary_keys.get(key, []),
                    is_foreign_key=foreign is not None,
                    referenced_schema=(
                        foreign["referenced_schema"] if foreign else None
                    ),
                    referenced_table=(foreign["referenced_table"] if foreign else None),
                    referenced_column=(
                        foreign["referenced_column"] if foreign else None
                    ),
                    description=mapping["description"],
                )
            )
        tables_by_schema: dict[str, list[DiscoveredTable]] = {}
        for row in table_rows:
            mapping = row  # type: ignore[assignment]
            key = (mapping["schema_name"], mapping["table_name"])
            tables_by_schema.setdefault(mapping["schema_name"], []).append(
                DiscoveredTable(
                    schema_name=mapping["schema_name"],
                    name=mapping["table_name"],
                    table_type=mapping["table_type"],
                    estimated_row_count=mapping["estimated_row_count"],
                    primary_key_columns=tuple(primary_keys.get(key, [])),
                    description=mapping["description"],
                    columns=tuple(columns_by_table.get(key, [])),
                )
            )
        return tuple(
            DiscoveredSchema(name=name, tables=tuple(tables))
            for name, tables in sorted(tables_by_schema.items())
        )

    @staticmethod
    def _categorize_error(exc: Exception) -> tuple[str, str]:
        chain: list[BaseException] = []
        current: BaseException | None = exc
        while current is not None and current not in chain:
            chain.append(current)
            current = current.__cause__ or current.__context__
        if any(isinstance(error, asyncpg.InvalidPasswordError) for error in chain):
            return "AUTHENTICATION_FAILED", "Database authentication failed"
        if any(isinstance(error, asyncpg.InvalidCatalogNameError) for error in chain):
            return "DATABASE_NOT_FOUND", "Database was not found"
        if any(
            isinstance(error, (asyncio.TimeoutError, TimeoutError)) for error in chain
        ):
            return "TIMEOUT", "Database connection timed out"
        if any(isinstance(error, ssl.SSLError) for error in chain):
            return "SSL_ERROR", "Database SSL negotiation failed"
        if any(
            isinstance(error, (ConnectionRefusedError, OperationalError))
            for error in chain
        ):
            return "CONNECTION_REFUSED", "Database connection was refused"
        if any(
            isinstance(error, (DBAPIError, SQLAlchemyError, OSError)) for error in chain
        ):
            return "CONNECTION_FAILED", "Database connection failed"
        return "CONNECTION_FAILED", "Database connection failed"
