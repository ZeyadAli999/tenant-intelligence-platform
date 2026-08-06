"""Registry that isolates orchestration code from concrete database dialects."""

from services.database.adapters.base import DatabaseAdapter


class UnsupportedDatabaseTypeError(Exception):
    """Raised when no deliberately supported adapter is registered."""


class AdapterRegistry:
    def __init__(self, adapters: tuple[DatabaseAdapter, ...]) -> None:
        self._adapters = {adapter.database_type: adapter for adapter in adapters}

    def resolve(self, database_type: str) -> DatabaseAdapter:
        try:
            return self._adapters[database_type.strip().casefold()]
        except KeyError as exc:
            raise UnsupportedDatabaseTypeError from exc

    @property
    def supported_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def build_adapter_registry() -> AdapterRegistry:
    """Build the deliberate support allowlist without importing in route code."""
    from services.database.adapters.postgresql import PostgreSQLAdapter

    return AdapterRegistry((PostgreSQLAdapter(),))
