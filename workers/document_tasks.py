"""Idempotent document processing actor using identifier-only messages."""

import asyncio
import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import dramatiq
from dramatiq.middleware import CurrentMessage
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from database.session import AsyncSessionFactory, dispose_engine
from models import DocumentChunk, StoredFile
from services.documents.chunker import chunk_document
from services.documents.embeddings import FastEmbedService
from services.documents.parsers.registry import ParserRegistry
from services.documents.upload_security import (
    FileValidationError,
    detect_type,
    inspect_container,
)
from storage.minio_store import MinioObjectStore
from workers.broker import configure_broker

configure_broker()

MAX_RETRIES = 2


class RetryableDocumentError(Exception):
    """Sanitized signal which Dramatiq may retry without exposing its cause."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dramatiq.actor(max_retries=MAX_RETRIES, min_backoff=1000, time_limit=900_000)
def process_document(tenant_id: str, file_id: str, ingestion_version: int) -> None:
    tenant_uuid = UUID(tenant_id)
    file_uuid = UUID(file_id)
    try:
        asyncio.run(_process(tenant_uuid, file_uuid, ingestion_version))
    except RetryableDocumentError as exc:
        if _current_retry_count() >= MAX_RETRIES:
            asyncio.run(
                _mark_failed(tenant_uuid, file_uuid, ingestion_version, exc.code)
            )
            return
        raise


async def _process(tenant_id: UUID, file_id: UUID, version: int) -> None:
    settings = get_settings()
    store = MinioObjectStore(settings)
    temporary = Path(tempfile.mkstemp(prefix="ingestion-", suffix=".document")[1])
    try:
        async with AsyncSessionFactory() as session:
            row = await session.scalar(
                select(StoredFile).where(
                    StoredFile.tenant_id == tenant_id, StoredFile.id == file_id
                )
            )
            if (
                row is None
                or row.deleted_at is not None
                or row.ingestion_version != version
            ):
                return
            row.processing_status = "processing"
            row.processing_started_at = datetime.now(UTC)
            row.processing_attempts += 1
            await session.commit()
            try:
                await store.download_to_file(
                    row.storage_bucket, row.object_key, temporary
                )
            except (TimeoutError, OSError) as exc:
                raise RetryableDocumentError("STORAGE_TEMPORARILY_UNAVAILABLE") from exc
            if temporary.stat().st_size != row.file_size_bytes:
                raise FileValidationError("STORAGE_INTEGRITY_FAILED")
            checksum = await asyncio.to_thread(_checksum, temporary)
            if checksum != row.checksum:
                raise FileValidationError("STORAGE_INTEGRITY_FAILED")
            if detect_type(temporary, row.extension) != row.detected_mime_type:
                raise FileValidationError("MIME_MISMATCH")
            inspect_container(temporary, row.extension)
            parsed = await asyncio.to_thread(
                ParserRegistry(settings).resolve(row.extension).parse, temporary
            )
            extracted = sum(len(element.text) for element in parsed.elements)
            if extracted > settings.document_max_extracted_characters:
                raise FileValidationError("CONTENT_LIMIT_EXCEEDED")
            drafts = chunk_document(parsed, settings)
            try:
                vectors = await asyncio.to_thread(
                    FastEmbedService(settings).embed, [item.content for item in drafts]
                )
            except (TimeoutError, OSError) as exc:
                raise RetryableDocumentError(
                    "EMBEDDING_TEMPORARILY_UNAVAILABLE"
                ) from exc
            if len(vectors) != len(drafts) or any(
                len(vector) != settings.embedding_dimension for vector in vectors
            ):
                raise FileValidationError("EMBEDDING_FAILED")
            current = await session.scalar(
                select(StoredFile)
                .where(StoredFile.tenant_id == tenant_id, StoredFile.id == file_id)
                .with_for_update()
            )
            if (
                current is None
                or current.deleted_at is not None
                or current.ingestion_version != version
            ):
                await session.rollback()
                return
            await session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.file_id == file_id,
                    DocumentChunk.ingestion_version == version,
                )
            )
            session.add_all(
                [
                    DocumentChunk(
                        tenant_id=tenant_id,
                        knowledge_base_id=current.knowledge_base_id,
                        file_id=file_id,
                        ingestion_version=version,
                        chunk_index=draft.index,
                        content=draft.content,
                        content_hash=draft.content_hash,
                        page_number=draft.page_number,
                        section_title=draft.section_title,
                        sheet_name=draft.sheet_name,
                        row_start=draft.row_start,
                        row_end=draft.row_end,
                        token_count=draft.token_count,
                        chunk_metadata=draft.metadata,
                        embedding=vector,
                    )
                    for draft, vector in zip(drafts, vectors, strict=True)
                ]
            )
            current.processing_status = "ready"
            current.active_ingestion_version = version
            current.processing_error_code = None
            current.processing_error_message = None
            current.page_count = parsed.page_count
            current.extracted_text_length = extracted
            current.chunk_count = len(drafts)
            current.processed_at = datetime.now(UTC)
            await session.commit()
    except FileValidationError as exc:
        await _mark_failed(tenant_id, file_id, version, exc.code)
    except RetryableDocumentError:
        await _mark_retry_pending(tenant_id, file_id, version)
        raise
    except (OperationalError, TimeoutError, OSError) as exc:
        await _mark_retry_pending(tenant_id, file_id, version)
        raise RetryableDocumentError("INFRASTRUCTURE_TEMPORARILY_UNAVAILABLE") from exc
    except Exception as exc:
        await _mark_retry_pending(tenant_id, file_id, version)
        raise RetryableDocumentError("DOCUMENT_PROCESSING_FAILED") from exc
    finally:
        temporary.unlink(missing_ok=True)
        await dispose_engine()


async def _mark_failed(tenant_id: UUID, file_id: UUID, version: int, code: str) -> None:
    async with AsyncSessionFactory() as session:
        row = await session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.id == file_id,
                StoredFile.ingestion_version == version,
                StoredFile.deleted_at.is_(None),
            )
        )
        if row is not None:
            row.processing_status = (
                "ready" if row.active_ingestion_version > 0 else "failed"
            )
            row.processing_error_code = code
            row.processing_error_message = "Document processing failed safely"
            await session.commit()


async def _mark_retry_pending(tenant_id: UUID, file_id: UUID, version: int) -> None:
    async with AsyncSessionFactory() as session:
        row = await session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.id == file_id,
                StoredFile.ingestion_version == version,
                StoredFile.deleted_at.is_(None),
            )
        )
        if row is not None:
            row.processing_status = (
                "ready" if row.active_ingestion_version > 0 else "pending"
            )
            row.processing_error_code = "RETRY_PENDING"
            row.processing_error_message = None
            await session.commit()


def _current_retry_count() -> int:
    message = CurrentMessage.get_current_message()
    if message is None:
        return 0
    return int(message.options.get("retries", 0))


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
