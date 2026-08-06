"""Secure file lifecycle spanning PostgreSQL, object storage, and identifier queue."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exceptions import ConflictError, ResourceNotFoundError
from core.tenant_context import TenantContext
from models import StoredFile
from repositories.documents import DocumentRepository
from services.documents.access_policy import KnowledgeBaseAccessPolicy
from services.documents.upload_security import stream_and_validate
from storage.object_store import ObjectStore
from workers.broker import DocumentQueue


class FileService:
    def __init__(
        self,
        session: AsyncSession,
        context: TenantContext,
        settings: Settings,
        object_store: ObjectStore,
        queue: DocumentQueue,
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings
        self.object_store = object_store
        self.queue = queue
        self.repository = DocumentRepository(session)
        self.policy = KnowledgeBaseAccessPolicy(self.repository, context)

    async def upload(self, knowledge_base_id: UUID, upload: UploadFile) -> StoredFile:
        await self.policy.require(knowledge_base_id, manage=True, active=True)
        validated = await stream_and_validate(upload, self.settings)
        try:
            if await self.repository.find_duplicate(
                self.context.tenant.id, knowledge_base_id, validated.checksum
            ):
                raise ConflictError
            file_id = uuid4()
            object_key = f"tenants/{self.context.tenant.id.hex}/{file_id.hex}"
            await self.object_store.put_file(
                self.settings.minio_bucket,
                object_key,
                validated.path,
                validated.checksum,
            )
            row = StoredFile(
                id=file_id,
                tenant_id=self.context.tenant.id,
                knowledge_base_id=knowledge_base_id,
                uploaded_by=self.context.user.id,
                original_name=validated.display_name,
                object_key=object_key,
                storage_bucket=self.settings.minio_bucket,
                mime_type=validated.detected_mime_type,
                detected_mime_type=validated.detected_mime_type,
                extension=validated.extension,
                file_size_bytes=validated.size,
                checksum=validated.checksum,
            )
            self.session.add(row)
            try:
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                await self.object_store.delete(self.settings.minio_bucket, object_key)
                raise
            self.queue.enqueue(row.tenant_id, row.id, row.ingestion_version)
            await self.session.refresh(row)
            return row
        finally:
            Path(validated.path).unlink(missing_ok=True)

    async def require_file(self, file_id: UUID, *, manage: bool = False) -> StoredFile:
        row = await self.repository.get_file(self.context.tenant.id, file_id)
        if row is None:
            raise ResourceNotFoundError
        await self.policy.require(row.knowledge_base_id, manage=manage)
        return row

    async def delete(self, file_id: UUID) -> None:
        row = await self.repository.get_file(
            self.context.tenant.id, file_id, include_deleted=True
        )
        if row is None:
            raise ResourceNotFoundError
        await self.policy.require(row.knowledge_base_id, manage=True)
        if row.processing_status == "deleted":
            return
        row.processing_status = "deleting"
        await self.session.commit()
        await self.object_store.delete(row.storage_bucket, row.object_key)
        row.processing_status = "deleted"
        row.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def reprocess(self, file_id: UUID) -> StoredFile:
        row = await self.require_file(file_id, manage=True)
        if row.processing_status in ("pending", "processing"):
            return row
        row.ingestion_version += 1
        row.processing_status = "pending"
        row.processing_error_code = None
        row.processing_error_message = None
        await self.session.commit()
        self.queue.enqueue(row.tenant_id, row.id, row.ingestion_version)
        await self.session.refresh(row)
        return row
