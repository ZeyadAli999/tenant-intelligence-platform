"""Tenant-isolated CRUD, testing, discovery, and cache orchestration."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.exceptions import (
    ConflictError,
    ConnectionNotReadyError,
    InvalidDatabaseHostError,
    ResourceNotFoundError,
)
from app.exceptions import (
    UnsupportedDatabaseTypeError as APIUnsupportedDatabaseTypeError,
)
from core.encryption import CredentialCipher, credential_context
from core.security import utc_now
from models import DatabaseColumn, DatabaseConnection, DatabaseSchema, DatabaseTable
from models.database_connection import (
    normalize_connection_name,
    normalize_database_type,
)
from repositories.database_connections import DatabaseConnectionRepository
from schemas.database_connections import (
    ConnectionTestResponse,
    DatabaseColumnResponse,
    DatabaseConnectionCreateRequest,
    DatabaseConnectionListResponse,
    DatabaseConnectionResponse,
    DatabaseConnectionUpdateRequest,
    DatabaseSchemaListResponse,
    DatabaseSchemaResponse,
    DatabaseTableListResponse,
    DatabaseTableResponse,
    SchemaSyncResponse,
)
from services.database.connection_tester import ConnectionTester
from services.database.dialect_resolver import (
    AdapterRegistry,
    UnsupportedDatabaseTypeError,
    build_adapter_registry,
)
from services.database.host_security import (
    HostSecurityError,
    HostSecurityValidator,
)
from services.database.metadata_cache import MetadataCacheService
from services.database.schema_discovery import SchemaDiscoveryService

logger = logging.getLogger(__name__)


def connection_response(connection: DatabaseConnection) -> DatabaseConnectionResponse:
    return DatabaseConnectionResponse.model_validate(connection)


def schema_response(schema: DatabaseSchema) -> DatabaseSchemaResponse:
    return DatabaseSchemaResponse.model_validate(schema)


def column_response(column: DatabaseColumn) -> DatabaseColumnResponse:
    return DatabaseColumnResponse.model_validate(column)


def table_response(
    table: DatabaseTable,
    schema: DatabaseSchema,
    columns: list[DatabaseColumn],
) -> DatabaseTableResponse:
    return DatabaseTableResponse(
        id=table.id,
        schema_name=schema.schema_name,
        table_name=table.table_name,
        table_type=table.table_type,
        description=table.description,
        estimated_row_count=table.estimated_row_count,
        primary_key_columns=table.primary_key_columns,
        is_enabled=table.is_enabled,
        is_sensitive=table.is_sensitive,
        columns=[column_response(column) for column in columns],
        created_at=table.created_at,
        updated_at=table.updated_at,
    )


class DatabaseConnectionService:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        settings: Settings | None = None,
        registry: AdapterRegistry | None = None,
        host_validator: HostSecurityValidator | None = None,
        cipher: CredentialCipher | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.settings = settings or get_settings()
        self.repository = DatabaseConnectionRepository(session)
        self.registry = registry or build_adapter_registry()
        self.host_validator = host_validator or HostSecurityValidator(
            allow_private=self.settings.allow_private_database_hosts
        )
        self.cipher = cipher or CredentialCipher.from_settings(self.settings)

    def _require_supported(self, database_type: str) -> str:
        normalized = normalize_database_type(database_type)
        try:
            self.registry.resolve(normalized)
        except UnsupportedDatabaseTypeError as exc:
            raise APIUnsupportedDatabaseTypeError from exc
        return normalized

    def _require_host(self, host: str, port: int) -> str:
        try:
            return self.host_validator.validate_host(host, port)
        except HostSecurityError as exc:
            raise InvalidDatabaseHostError from exc

    async def create(
        self,
        payload: DatabaseConnectionCreateRequest,
        *,
        created_by: UUID,
    ) -> DatabaseConnectionResponse:
        database_type = self._require_supported(payload.database_type)
        host = self._require_host(payload.host, payload.port)
        connection = DatabaseConnection(
            id=uuid4(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            name=normalize_connection_name(payload.name),
            database_type=database_type,
            host=host,
            port=payload.port,
            database_name=payload.database_name.strip(),
            username=payload.username.strip(),
            encrypted_password="pending",
            ssl_enabled=payload.ssl_enabled,
            ssl_settings=payload.ssl_settings.model_dump(),
            connection_options=payload.connection_options.model_dump(),
        )
        connection.encrypted_password = self.cipher.encrypt(
            payload.password.get_secret_value(),
            associated_data=credential_context(self.tenant_id, connection.id),
        )
        self.session.add(connection)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(connection)
        return connection_response(connection)

    async def get(self, connection_id: UUID) -> DatabaseConnectionResponse:
        return connection_response(await self._get_connection(connection_id))

    async def list(
        self, *, page: int, page_size: int
    ) -> DatabaseConnectionListResponse:
        rows, total = await self.repository.list_connections(
            self.tenant_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return DatabaseConnectionListResponse(
            items=[connection_response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(
        self,
        connection_id: UUID,
        payload: DatabaseConnectionUpdateRequest,
    ) -> DatabaseConnectionResponse:
        connection = await self._get_connection(connection_id)
        changed = payload.model_fields_set
        connection_details_changed = bool(
            changed
            & {
                "database_type",
                "host",
                "port",
                "database_name",
                "username",
                "password",
                "ssl_enabled",
                "ssl_settings",
                "connection_options",
            }
        )
        if "name" in changed and payload.name is not None:
            connection.name = normalize_connection_name(payload.name)
        if "database_type" in changed and payload.database_type is not None:
            connection.database_type = self._require_supported(payload.database_type)
        candidate_host = payload.host if payload.host is not None else connection.host
        candidate_port = payload.port if payload.port is not None else connection.port
        if "host" in changed or "port" in changed:
            connection.host = self._require_host(candidate_host, candidate_port)
            connection.port = candidate_port
        for field_name in ("database_name", "username"):
            value = getattr(payload, field_name)
            if field_name in changed and value is not None:
                setattr(connection, field_name, value.strip())
        if "ssl_enabled" in changed and payload.ssl_enabled is not None:
            connection.ssl_enabled = payload.ssl_enabled
        if "ssl_settings" in changed and payload.ssl_settings is not None:
            connection.ssl_settings = payload.ssl_settings.model_dump()
        if "connection_options" in changed and payload.connection_options is not None:
            connection.connection_options = payload.connection_options.model_dump()
        if "password" in changed and payload.password is not None:
            connection.encrypted_password = self.cipher.encrypt(
                payload.password.get_secret_value(),
                associated_data=credential_context(self.tenant_id, connection.id),
            )
        if connection_details_changed:
            connection.status = "pending"
            connection.last_tested_at = None
            connection.last_test_message = None
            connection.schema_sync_status = "pending"
            connection.last_schema_sync_at = None
            await self.repository.reconcile_metadata(
                tenant_id=self.tenant_id,
                connection_id=connection.id,
                discovered=(),
            )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(connection)
        return connection_response(connection)

    async def delete(self, connection_id: UUID) -> None:
        connection = await self._get_connection(connection_id)
        connection.is_active = False
        connection.status = "pending"
        connection.schema_sync_status = "pending"
        await self.session.commit()

    async def test_connection(
        self,
        connection_id: UUID,
        *,
        request_id: str,
    ) -> ConnectionTestResponse:
        connection = await self._get_connection(connection_id)
        tester = ConnectionTester(
            registry=self.registry,
            cipher=self.cipher,
            host_validator=self.host_validator,
        )
        result = await tester.test(connection)
        tested_at = utc_now()
        connection.status = "connected" if result.success else "failed"
        connection.last_tested_at = tested_at
        connection.last_test_message = result.message
        await self.session.commit()
        logger.info(
            "Customer database test completed request_id=%r success=%s error_code=%s",
            request_id,
            result.success,
            result.error_code or "none",
        )
        return ConnectionTestResponse(
            success=result.success,
            status=connection.status,
            error_code=result.error_code,
            message=result.message,
            tested_at=tested_at,
        )

    async def sync_schema(
        self,
        connection_id: UUID,
        *,
        request_id: str,
    ) -> SchemaSyncResponse:
        connection = await self._get_connection(connection_id)
        if connection.status != "connected":
            raise ConnectionNotReadyError
        connection.schema_sync_status = "running"
        await self.session.commit()
        try:
            discovered = await SchemaDiscoveryService(
                registry=self.registry,
                cipher=self.cipher,
                host_validator=self.host_validator,
            ).discover(connection)
            counts = await MetadataCacheService(self.repository).reconcile(
                tenant_id=self.tenant_id,
                connection_id=connection.id,
                discovered=discovered,
            )
            synced_at = utc_now()
            connection.schema_sync_status = "succeeded"
            connection.last_schema_sync_at = synced_at
            await self.session.commit()
            logger.info(
                "Customer schema sync completed request_id=%r status=succeeded",
                request_id,
            )
            return SchemaSyncResponse(
                success=True,
                status="succeeded",
                message="Schema synchronization succeeded",
                schema_count=counts[0],
                table_count=counts[1],
                column_count=counts[2],
                synced_at=synced_at,
            )
        except Exception as exc:  # noqa: BLE001 - rollback and sanitize all adapter failures
            await self.session.rollback()
            current = await self._get_connection(connection_id)
            current.schema_sync_status = "failed"
            await self.session.commit()
            logger.warning(
                "Customer schema sync failed request_id=%r exception_type=%s",
                request_id,
                type(exc).__name__,
            )
            return SchemaSyncResponse(
                success=False,
                status="failed",
                message="Schema synchronization failed",
                schema_count=0,
                table_count=0,
                column_count=0,
                synced_at=None,
            )

    async def list_schemas(
        self,
        connection_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> DatabaseSchemaListResponse:
        await self._get_connection(connection_id)
        rows, total = await self.repository.list_schemas(
            self.tenant_id,
            connection_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return DatabaseSchemaListResponse(
            items=[schema_response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_tables(
        self,
        connection_id: UUID,
        *,
        page: int,
        page_size: int,
        schema_name: str | None,
        enabled: bool | None,
        table_type: str | None,
        search: str | None,
    ) -> DatabaseTableListResponse:
        await self._get_connection(connection_id)
        rows, total = await self.repository.list_tables(
            self.tenant_id,
            connection_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            schema_name=schema_name,
            enabled=enabled,
            table_type=table_type,
            search=search,
        )
        columns = await self.repository.columns_for_tables(
            self.tenant_id,
            [table.id for table, _ in rows],
        )
        return DatabaseTableListResponse(
            items=[
                table_response(table, schema, columns[table.id])
                for table, schema in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _get_connection(self, connection_id: UUID) -> DatabaseConnection:
        connection = await self.repository.get_connection(
            self.tenant_id,
            connection_id,
        )
        if connection is None:
            raise ResourceNotFoundError
        return connection
