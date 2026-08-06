"""Short-lived engine disposal, re-resolution, and safe failure tests."""

from typing import Self
from uuid import uuid4

import pytest

from app.config import Settings
from core.encryption import CredentialCipher, credential_context
from models import DatabaseConnection
from services.database.adapters.base import ConnectionParameters
from services.database.adapters.postgresql import PostgreSQLAdapter
from services.database.connection_tester import ConnectionTester
from services.database.dialect_resolver import AdapterRegistry
from services.database.host_security import HostSecurityValidator


class FakeConnection:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.executions: list[str] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: object) -> None:
        self.executions.append(str(statement))
        if self.failure is not None:
            raise self.failure


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    async def dispose(self) -> None:
        self.disposed = True


def parameters() -> ConnectionParameters:
    return ConnectionParameters(
        host="database.example.com",
        port=5432,
        database_name="customer",
        username="reader",
        password="secret",
        ssl_enabled=False,
        ssl_settings={},
        connection_options={},
    )


def adapter_settings() -> Settings:
    return Settings(
        connection_encryption_key=("AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"),
        customer_database_connect_timeout_seconds=0.5,
        customer_database_command_timeout_seconds=0.5,
    )


@pytest.mark.asyncio
async def test_engine_is_disposed_after_success() -> None:
    engine = FakeEngine(FakeConnection())
    adapter = PostgreSQLAdapter(
        settings=adapter_settings(),
        engine_factory=lambda _url, _options: engine,  # type: ignore[arg-type]
    )

    result = await adapter.test_connection(
        parameters(),
        HostSecurityValidator(
            allow_private=False,
            resolver=lambda _host, _port: public_resolution(),
        ),
    )

    assert result.success is True
    assert engine.disposed is True
    assert engine.connection.executions == ["SET TRANSACTION READ ONLY", "SELECT 1"]


@pytest.mark.asyncio
async def test_engine_is_disposed_and_error_is_sanitized_after_failure() -> None:
    raw_detail = "password=never-log-me host=private.internal"
    engine = FakeEngine(FakeConnection(ConnectionRefusedError(raw_detail)))
    adapter = PostgreSQLAdapter(
        settings=adapter_settings(),
        engine_factory=lambda _url, _options: engine,  # type: ignore[arg-type]
    )

    result = await adapter.test_connection(
        parameters(),
        HostSecurityValidator(
            allow_private=False,
            resolver=lambda _host, _port: public_resolution(),
        ),
    )

    assert result.success is False
    assert result.error_code == "CONNECTION_REFUSED"
    assert raw_detail not in result.message
    assert engine.disposed is True


@pytest.mark.asyncio
async def test_connection_tester_resolves_before_orchestration_and_adapter_connect() -> (
    None
):
    resolution_count = 0

    async def resolver(_: str, __: int) -> tuple[str, ...]:
        nonlocal resolution_count
        resolution_count += 1
        return ("8.8.8.8",)

    settings = adapter_settings()
    cipher = CredentialCipher.from_settings(settings)
    connection = DatabaseConnection(
        id=uuid4(),
        tenant_id=uuid4(),
        created_by=uuid4(),
        name="customer",
        database_type="postgresql",
        host="database.example.com",
        port=5432,
        database_name="customer",
        username="reader",
        encrypted_password="pending",
    )
    connection.encrypted_password = cipher.encrypt(
        "secret",
        associated_data=credential_context(connection.tenant_id, connection.id),
    )
    engine = FakeEngine(FakeConnection())
    adapter = PostgreSQLAdapter(
        settings=settings,
        engine_factory=lambda _url, _options: engine,  # type: ignore[arg-type]
    )
    validator = HostSecurityValidator(allow_private=False, resolver=resolver)

    result = await ConnectionTester(
        registry=AdapterRegistry((adapter,)),
        cipher=cipher,
        host_validator=validator,
    ).test(connection)

    assert result.success is True
    assert resolution_count == 2


async def public_resolution() -> tuple[str, ...]:
    return ("8.8.8.8",)
