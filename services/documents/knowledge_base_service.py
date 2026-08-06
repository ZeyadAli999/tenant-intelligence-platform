"""Knowledge-base lifecycle with owner/admin authorization."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exceptions import ConflictError
from core.tenant_context import TenantContext
from models import KnowledgeBase, StoredFile
from repositories.documents import DocumentRepository
from schemas.documents import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest
from services.documents.access_policy import KnowledgeBaseAccessPolicy
from storage.object_store import ObjectStore


class KnowledgeBaseService:
    def __init__(
        self, session: AsyncSession, context: TenantContext, settings: Settings
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings
        self.repository = DocumentRepository(session)
        self.policy = KnowledgeBaseAccessPolicy(self.repository, context)

    async def create(self, payload: KnowledgeBaseCreateRequest) -> KnowledgeBase:
        row = KnowledgeBase(
            tenant_id=self.context.tenant.id,
            created_by=self.context.user.id,
            name=payload.name.casefold(),
            description=payload.description,
            embedding_model=self.settings.embedding_model,
            embedding_dimension=self.settings.embedding_dimension,
            chunking_config={
                "target_tokens": self.settings.document_chunk_target_tokens,
                "overlap_tokens": self.settings.document_chunk_overlap_tokens,
            },
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(row)
        return row

    async def update(
        self, kb_id: UUID, payload: KnowledgeBaseUpdateRequest
    ) -> KnowledgeBase:
        row = await self.policy.require(kb_id, manage=True)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            updates["name"] = updates["name"].casefold()
        for field, value in updates.items():
            setattr(row, field, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError from exc
        await self.session.refresh(row)
        return row

    async def delete(
        self, kb_id: UUID, object_store: ObjectStore | None = None
    ) -> None:
        row = await self.policy.require(kb_id, manage=True)
        files = list(
            (
                await self.session.scalars(
                    select(StoredFile).where(
                        StoredFile.tenant_id == self.context.tenant.id,
                        StoredFile.knowledge_base_id == kb_id,
                        StoredFile.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        if object_store is not None:
            for file in files:
                await object_store.delete(file.storage_bucket, file.object_key)
        now = datetime.now(UTC)
        for file in files:
            file.processing_status = "deleted"
            file.deleted_at = now
        row.status = "deleted"
        await self.session.commit()
