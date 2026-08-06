"""SSRF host syntax, resolution, and private-network policy tests."""

import pytest

from services.database.host_security import (
    HostSecurityError,
    HostSecurityValidator,
    validate_host_format,
)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "::1",
        "169.254.169.254",
        "224.0.0.1",
        "0.0.0.0",
        "240.0.0.1",
    ],
)
def test_special_addresses_are_blocked(host: str) -> None:
    with pytest.raises(HostSecurityError):
        HostSecurityValidator(allow_private=False).validate_host(host, 5432)


@pytest.mark.parametrize(
    "host",
    [
        "postgresql://db.example.com/customer",
        "user@db.example.com",
        "db.example.com/path",
        "db.example.com?ssl=true",
        "db.example.com#fragment",
        "bad host.example",
    ],
)
def test_url_and_invalid_host_syntax_is_rejected(host: str) -> None:
    with pytest.raises(HostSecurityError):
        validate_host_format(host, 5432)


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_invalid_port_is_rejected(port: int) -> None:
    with pytest.raises(HostSecurityError):
        validate_host_format("db.example.com", port)


def test_private_address_requires_explicit_configuration() -> None:
    with pytest.raises(HostSecurityError):
        HostSecurityValidator(allow_private=False).validate_host("10.0.0.10", 5432)

    assert (
        HostSecurityValidator(allow_private=True).validate_host("10.0.0.10", 5432)
        == "10.0.0.10"
    )


@pytest.mark.asyncio
async def test_dns_resolution_results_are_all_validated() -> None:
    async def mixed_resolver(_: str, __: int) -> tuple[str, ...]:
        return "8.8.8.8", "127.0.0.1"

    validator = HostSecurityValidator(
        allow_private=False,
        resolver=mixed_resolver,
    )

    with pytest.raises(HostSecurityError):
        await validator.resolve_and_validate("database.example.com", 5432)


@pytest.mark.asyncio
async def test_public_dns_resolution_is_accepted() -> None:
    async def public_resolver(_: str, __: int) -> tuple[str, ...]:
        return ("8.8.8.8",)

    validator = HostSecurityValidator(
        allow_private=False,
        resolver=public_resolver,
    )

    assert await validator.resolve_and_validate("database.example.com", 5432) == (
        "8.8.8.8",
    )
