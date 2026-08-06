"""Tenant-filtered dense/lexical retrieval and deterministic RRF reranking."""

import math
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from models import DocumentChunk
from repositories.documents import DocumentRepository
from services.documents.embeddings import EmbeddingService

WORD = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence_id: str
    chunk: DocumentChunk
    score: float


class DocumentRetrievalService:
    def __init__(
        self, session: AsyncSession, settings: Settings, embeddings: EmbeddingService
    ) -> None:
        self.session = session
        self.settings = settings
        self.embeddings = embeddings
        self.repository = DocumentRepository(session)

    async def retrieve(
        self, tenant_id: UUID, kb_ids: list[UUID], query: str
    ) -> tuple[RetrievedEvidence, ...]:
        vector = self.embeddings.embed([query])[0]
        if len(vector) != self.settings.embedding_dimension:
            raise ValueError("Invalid query embedding dimension")
        if self.session.get_bind().dialect.name == "postgresql":
            dense = await self.repository.dense_candidates(
                tenant_id, kb_ids, vector, self.settings.document_dense_candidates
            )
            lexical = await self.repository.lexical_candidates(
                tenant_id, kb_ids, query, self.settings.document_lexical_candidates
            )
        else:
            chunks = await self.repository.active_chunks(tenant_id, kb_ids)
            dense = sorted(
                ((chunk, _cosine(vector, list(chunk.embedding))) for chunk in chunks),
                key=lambda item: item[1],
                reverse=True,
            )[: self.settings.document_dense_candidates]
            terms = set(WORD.findall(query.casefold()))
            lexical = sorted(
                (
                    (
                        chunk,
                        len(terms & set(WORD.findall(chunk.content.casefold())))
                        / max(len(terms), 1),
                    )
                    for chunk in chunks
                ),
                key=lambda item: item[1],
                reverse=True,
            )[: self.settings.document_lexical_candidates]
        merged: dict[UUID, tuple[DocumentChunk, float]] = {}
        for candidates in (dense, lexical):
            for rank, (chunk, _) in enumerate(candidates, 1):
                current = merged.get(chunk.id, (chunk, 0.0))[1]
                merged[chunk.id] = (chunk, current + 1.0 / (60 + rank))
        query_terms = set(WORD.findall(query.casefold()))
        scored: list[tuple[DocumentChunk, float, float]] = []
        for chunk, fusion in merged.values():
            dense_score = next(
                (value for item, value in dense if item.id == chunk.id), 0.0
            )
            lexical_score = next(
                (value for item, value in lexical if item.id == chunk.id), 0.0
            )
            content_terms = set(WORD.findall(chunk.content.casefold()))
            overlap = len(query_terms & content_terms) / max(len(query_terms), 1)
            metadata_quality = 0.02 * sum(
                value is not None
                for value in (
                    chunk.page_number,
                    chunk.section_title,
                    chunk.sheet_name,
                    chunk.row_start,
                )
            )
            rerank_score = (
                0.45 * max(dense_score, 0.0)
                + 0.30 * max(lexical_score, 0.0)
                + 0.20 * overlap
                + 0.05 * min(fusion * 60, 1.0)
                + metadata_quality
            )
            scored.append(
                (chunk, rerank_score, max(dense_score, lexical_score, overlap))
            )
        ordered = sorted(scored, key=lambda item: (-item[1], str(item[0].id)))
        selected: list[RetrievedEvidence] = []
        characters = 0
        hashes: set[str] = set()
        page_counts: dict[tuple[UUID, int | None], int] = {}
        for chunk, score, relevance in ordered:
            if relevance < self.settings.document_min_relevance:
                continue
            page_key = (chunk.file_id, chunk.page_number)
            if chunk.content_hash in hashes or page_counts.get(page_key, 0) >= 2:
                continue
            if (
                characters + len(chunk.content)
                > self.settings.document_max_evidence_characters
            ):
                continue
            selected.append(RetrievedEvidence(f"DOC{len(selected) + 1}", chunk, score))
            hashes.add(chunk.content_hash)
            page_counts[page_key] = page_counts.get(page_key, 0) + 1
            characters += len(chunk.content)
            if len(selected) >= self.settings.document_final_top_k:
                break
        return tuple(selected)


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return (
        sum(a * b for a, b in zip(left, right, strict=True)) / denominator
        if denominator
        else 0.0
    )
