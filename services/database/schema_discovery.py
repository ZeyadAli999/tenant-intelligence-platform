"""Database-neutral orchestration for metadata-only schema discovery."""

from core.encryption import CredentialCipher, credential_context
from models import DatabaseConnection
from services.database.adapters.base import DiscoveredSchema
from services.database.connection_tester import connection_parameters
from services.database.dialect_resolver import AdapterRegistry
from services.database.host_security import HostSecurityValidator


class SchemaDiscoveryService:
    def __init__(
        self,
        *,
        registry: AdapterRegistry,
        cipher: CredentialCipher,
        host_validator: HostSecurityValidator,
    ) -> None:
        self.registry = registry
        self.cipher = cipher
        self.host_validator = host_validator

    async def discover(
        self,
        connection: DatabaseConnection,
    ) -> tuple[DiscoveredSchema, ...]:
        password = self.cipher.decrypt(
            connection.encrypted_password,
            associated_data=credential_context(connection.tenant_id, connection.id),
        )
        await self.host_validator.resolve_and_validate(connection.host, connection.port)
        adapter = self.registry.resolve(connection.database_type)
        return await adapter.discover_schema(
            connection_parameters(connection, password),
            self.host_validator,
        )
