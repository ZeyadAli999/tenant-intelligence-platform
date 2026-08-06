"""Redis broker carrying document identifiers only."""

from functools import lru_cache
from typing import Protocol
from uuid import UUID

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage

from app.config import Settings, get_settings


class DocumentQueue(Protocol):
    def enqueue(
        self, tenant_id: UUID, file_id: UUID, ingestion_version: int
    ) -> None: ...


class DramatiqDocumentQueue:
    def enqueue(self, tenant_id: UUID, file_id: UUID, ingestion_version: int) -> None:
        from workers.document_tasks import process_document

        process_document.send(str(tenant_id), str(file_id), ingestion_version)


@lru_cache
def configure_broker(settings: Settings | None = None) -> RedisBroker:
    resolved = settings or get_settings()
    broker = RedisBroker(url=resolved.redis_url)
    broker.add_middleware(CurrentMessage())
    dramatiq.set_broker(broker)
    return broker


def get_document_queue() -> DocumentQueue:
    configure_broker()
    return DramatiqDocumentQueue()
