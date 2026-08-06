"""Tenant-first document persistence and retrieval primitives."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DocumentChunk, KnowledgeBase, MessageCitation, StoredFile


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_kb(
        self, tenant_id: UUID, knowledge_base_id: UUID, *, active: bool = False
    ) -> KnowledgeBase | None:
        query = select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.status != "deleted",
        )
        if active:
            query = query.where(KnowledgeBase.status == "active")
        return await self.session.scalar(query)

    async def list_kbs(
        self, tenant_id: UUID, user_id: UUID, is_admin: bool, page: int, page_size: int
    ) -> tuple[list[KnowledgeBase], int]:
        criteria = [
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.status != "deleted",
        ]
        if not is_admin:
            criteria.append(KnowledgeBase.created_by == user_id)
        total = await self.session.scalar(
            select(func.count()).select_from(KnowledgeBase).where(*criteria)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(KnowledgeBase)
                    .where(*criteria)
                    .order_by(KnowledgeBase.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def get_file(
        self, tenant_id: UUID, file_id: UUID, *, include_deleted: bool = False
    ) -> StoredFile | None:
        query = select(StoredFile).where(
            StoredFile.tenant_id == tenant_id,
            StoredFile.id == file_id,
        )
        if not include_deleted:
            query = query.where(StoredFile.processing_status != "deleted")
        return await self.session.scalar(query)

    async def find_duplicate(
        self, tenant_id: UUID, kb_id: UUID, checksum: str
    ) -> StoredFile | None:
        return await self.session.scalar(
            select(StoredFile).where(
                StoredFile.tenant_id == tenant_id,
                StoredFile.knowledge_base_id == kb_id,
                StoredFile.checksum == checksum,
                StoredFile.deleted_at.is_(None),
            )
        )

    async def list_files(
        self,
        tenant_id: UUID,
        allowed_kb_ids: Sequence[UUID],
        page: int,
        page_size: int,
        *,
        knowledge_base_id: UUID | None = None,
        processing_status: str | None = None,
        extension: str | None = None,
    ) -> tuple[list[StoredFile], int]:
        criteria = [
            StoredFile.tenant_id == tenant_id,
            StoredFile.knowledge_base_id.in_(allowed_kb_ids),
            StoredFile.processing_status != "deleted",
        ]
        if knowledge_base_id:
            criteria.append(StoredFile.knowledge_base_id == knowledge_base_id)
        if processing_status:
            criteria.append(StoredFile.processing_status == processing_status)
        if extension:
            criteria.append(StoredFile.extension == extension.casefold())
        total = await self.session.scalar(
            select(func.count()).select_from(StoredFile).where(*criteria)
        )
        rows = list(
            (
                await self.session.scalars(
                    select(StoredFile)
                    .where(*criteria)
                    .order_by(StoredFile.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return rows, int(total or 0)

    async def active_chunks(
        self, tenant_id: UUID, kb_ids: Sequence[UUID]
    ) -> list[DocumentChunk]:
        return list(
            (
                await self.session.scalars(
                    select(DocumentChunk)
                    .join(StoredFile, StoredFile.id == DocumentChunk.file_id)
                    .where(
                        DocumentChunk.tenant_id == tenant_id,
                        DocumentChunk.knowledge_base_id.in_(kb_ids),
                        StoredFile.processing_status.in_(("ready", "processing")),
                        StoredFile.active_ingestion_version > 0,
                        StoredFile.deleted_at.is_(None),
                        DocumentChunk.ingestion_version
                        == StoredFile.active_ingestion_version,
                    )
                )
            ).all()
        )

    async def dense_candidates(
        self, tenant_id: UUID, kb_ids: Sequence[UUID], vector: list[float], limit: int
    ) -> list[tuple[DocumentChunk, float]]:
        distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
        rows = (
            await self.session.execute(
                select(DocumentChunk, distance)
                .join(StoredFile, StoredFile.id == DocumentChunk.file_id)
                .where(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.knowledge_base_id.in_(kb_ids),
                    StoredFile.tenant_id == tenant_id,
                    StoredFile.processing_status.in_(("ready", "processing")),
                    StoredFile.active_ingestion_version > 0,
                    StoredFile.deleted_at.is_(None),
                    DocumentChunk.ingestion_version
                    == StoredFile.active_ingestion_version,
                )
                .order_by(distance)
                .limit(limit)
            )
        ).all()
        return [
            (chunk, max(0.0, 1.0 - float(distance_value)))
            for chunk, distance_value in rows
        ]

    async def lexical_candidates(
        self, tenant_id: UUID, kb_ids: Sequence[UUID], query: str, limit: int
    ) -> list[tuple[DocumentChunk, float]]:
        document_vector = func.to_tsvector("simple", DocumentChunk.content)
        query_vector = func.plainto_tsquery("simple", query)
        rank = func.ts_rank_cd(document_vector, query_vector).label("rank")
        rows = (
            await self.session.execute(
                select(DocumentChunk, rank)
                .join(StoredFile, StoredFile.id == DocumentChunk.file_id)
                .where(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.knowledge_base_id.in_(kb_ids),
                    StoredFile.tenant_id == tenant_id,
                    StoredFile.processing_status.in_(("ready", "processing")),
                    StoredFile.active_ingestion_version > 0,
                    StoredFile.deleted_at.is_(None),
                    DocumentChunk.ingestion_version
                    == StoredFile.active_ingestion_version,
                    document_vector.op("@@")(query_vector),
                )
                .order_by(rank.desc())
                .limit(limit)
            )
        ).all()
        return [(chunk, float(score)) for chunk, score in rows]

    async def citations(
        self, tenant_id: UUID, message_id: UUID
    ) -> list[MessageCitation]:
        return list(
            (
                await self.session.scalars(
                    select(MessageCitation)
                    .where(
                        MessageCitation.tenant_id == tenant_id,
                        MessageCitation.message_id == message_id,
                    )
                    .order_by(MessageCitation.created_at, MessageCitation.id)
                )
            ).all()
        )
