"""Database-agnostic adapter contracts and discovery value objects."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from services.database.host_security import HostSecurityValidator


@dataclass(frozen=True)
class ConnectionParameters:
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_enabled: bool
    ssl_settings: dict[str, object]
    connection_options: dict[str, object]


@dataclass(frozen=True)
class AdapterTestResult:
    success: bool
    error_code: str | None
    message: str


@dataclass(frozen=True)
class QueryLimits:
    statement_timeout_ms: int
    lock_timeout_ms: int
    max_rows: int
    max_columns: int


@dataclass(frozen=True)
class AdapterQueryResult:
    columns: tuple[str, ...]
    rows: tuple[dict[str, object], ...]
    truncated: bool


@dataclass(frozen=True)
class DiscoveredColumn:
    name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_schema: str | None = None
    referenced_table: str | None = None
    referenced_column: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class DiscoveredTable:
    schema_name: str
    name: str
    table_type: str
    estimated_row_count: int | None
    primary_key_columns: tuple[str, ...] = ()
    description: str | None = None
    columns: tuple[DiscoveredColumn, ...] = ()


@dataclass(frozen=True)
class DiscoveredSchema:
    name: str
    description: str | None = None
    tables: tuple[DiscoveredTable, ...] = field(default_factory=tuple)


class DatabaseAdapter(ABC):
    database_type: str

    @abstractmethod
    async def test_connection(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> AdapterTestResult:
        """Test a short-lived read-only connection."""

    @abstractmethod
    async def discover_schema(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
    ) -> tuple[DiscoveredSchema, ...]:
        """Read customer metadata without reading business rows."""

    async def execute_query(
        self,
        parameters: ConnectionParameters,
        host_validator: HostSecurityValidator,
        sql: str,
        bound_parameters: dict[str, object],
        limits: QueryLimits,
    ) -> AdapterQueryResult:
        """Execute one prevalidated read-only query with hard limits."""
        raise NotImplementedError
