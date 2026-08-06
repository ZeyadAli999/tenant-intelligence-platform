"""Reusable SSRF and DNS-rebinding defenses for customer database hosts."""

import asyncio
import ipaddress
import re
import socket
from collections.abc import Awaitable, Callable

Resolver = Callable[[str, int], Awaitable[tuple[str, ...]]]
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_METADATA_ADDRESSES = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


class HostSecurityError(Exception):
    """A safe host-policy rejection without resolved-address detail."""


def validate_host_format(host: str, port: int) -> str:
    """Reject URL-like or malformed host input before DNS is consulted."""
    normalized = host.strip()
    if not normalized or len(normalized) > 255 or not 1 <= port <= 65535:
        raise HostSecurityError
    try:
        ipaddress.ip_address(normalized)
        return normalized
    except ValueError:
        pass
    if any(character in normalized for character in ("/", "\\", "?", "#", "@", ":")):
        raise HostSecurityError
    normalized = normalized.removesuffix(".")
    labels = normalized.split(".")
    if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise HostSecurityError
    return normalized.casefold()


def _validate_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_private: bool
) -> None:
    if (
        address in _METADATA_ADDRESSES
        or address.is_unspecified
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    ):
        raise HostSecurityError
    if address.is_private and not allow_private:
        raise HostSecurityError


async def _system_resolver(host: str, port: int) -> tuple[str, ...]:
    loop = asyncio.get_running_loop()
    records = await loop.run_in_executor(
        None,
        lambda: socket.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        ),
    )
    return tuple(dict.fromkeys(record[4][0] for record in records))


class HostSecurityValidator:
    def __init__(
        self,
        *,
        allow_private: bool,
        resolver: Resolver | None = None,
    ) -> None:
        self.allow_private = allow_private
        self.resolver = resolver or _system_resolver

    def validate_host(self, host: str, port: int) -> str:
        """Validate syntax and immediately reject unsafe literal IP addresses."""
        normalized = validate_host_format(host, port)
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            return normalized
        _validate_address(address, allow_private=self.allow_private)
        return normalized

    async def resolve_and_validate(self, host: str, port: int) -> tuple[str, ...]:
        normalized = self.validate_host(host, port)
        try:
            resolved = await self.resolver(normalized, port)
        except (OSError, socket.gaierror) as exc:
            raise HostSecurityError from exc
        if not resolved:
            raise HostSecurityError
        addresses: list[str] = []
        for value in resolved:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise HostSecurityError from exc
            _validate_address(address, allow_private=self.allow_private)
            addresses.append(str(address))
        return tuple(dict.fromkeys(addresses))
