"""Credential-scoped orchestration for safe customer connection tests."""

from core.encryption import (
    CredentialCipher,
    CredentialDecryptionError,
    credential_context,
)
from models import DatabaseConnection
from services.database.adapters.base import AdapterTestResult, ConnectionParameters
from services.database.dialect_resolver import AdapterRegistry
from services.database.host_security import HostSecurityError, HostSecurityValidator


def connection_parameters(
    connection: DatabaseConnection,
    password: str,
) -> ConnectionParameters:
    return ConnectionParameters(
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.username,
        password=password,
        ssl_enabled=connection.ssl_enabled or False,
        ssl_settings=connection.ssl_settings or {},
        connection_options=connection.connection_options or {},
    )


class ConnectionTester:
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

    async def test(self, connection: DatabaseConnection) -> AdapterTestResult:
        try:
            password = self.cipher.decrypt(
                connection.encrypted_password,
                associated_data=credential_context(connection.tenant_id, connection.id),
            )
        except CredentialDecryptionError:
            return AdapterTestResult(
                False,
                "CREDENTIAL_DECRYPTION_FAILED",
                "Stored database credentials are unavailable",
            )
        try:
            await self.host_validator.resolve_and_validate(
                connection.host,
                connection.port,
            )
        except HostSecurityError:
            return AdapterTestResult(
                False,
                "HOST_BLOCKED",
                "Database host is not allowed",
            )
        adapter = self.registry.resolve(connection.database_type)
        return await adapter.test_connection(
            connection_parameters(connection, password),
            self.host_validator,
        )
