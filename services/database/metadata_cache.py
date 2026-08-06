"""Transactional identity-preserving reconciliation of customer metadata."""

from uuid import UUID

from repositories.database_connections import DatabaseConnectionRepository
from services.database.adapters.base import DiscoveredSchema


class MetadataCacheService:
    def __init__(self, repository: DatabaseConnectionRepository) -> None:
        self.repository = repository

    async def reconcile(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        discovered: tuple[DiscoveredSchema, ...],
    ) -> tuple[int, int, int]:
        return await self.repository.reconcile_metadata(
            tenant_id=tenant_id,
            connection_id=connection_id,
            discovered=discovered,
        )
