"""Real PostgreSQL pgvector retrieval and document tenant constraints."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.security import hash_password
from models import DocumentChunk, KnowledgeBase, StoredFile, Tenant, User
from repositories.documents import DocumentRepository
from tests.integration.test_migrations import run_alembic

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pgvector_index_and_tenant_filtered_candidates(
    postgres_test_url: str,
) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    engine = create_async_engine(postgres_test_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_a = Tenant(id=uuid4(), name="Documents A", code=f"docs-a-{uuid4().hex}")
    tenant_b = Tenant(id=uuid4(), name="Documents B", code=f"docs-b-{uuid4().hex}")
    user_a = User(
        id=uuid4(),
        tenant_id=tenant_a.id,
        email="docs@example.test",
        password_hash=hash_password("Integration-Documents-Password-99"),
    )
    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email="docs@example.test",
        password_hash=hash_password("Integration-Documents-Password-99"),
    )
    kb_a = KnowledgeBase(
        id=uuid4(),
        tenant_id=tenant_a.id,
        created_by=user_a.id,
        name="contracts",
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        embedding_dimension=384,
    )
    kb_b = KnowledgeBase(
        id=uuid4(),
        tenant_id=tenant_b.id,
        created_by=user_b.id,
        name="contracts",
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        embedding_dimension=384,
    )
    file_a = StoredFile(
        id=uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_a.id,
        uploaded_by=user_a.id,
        original_name="a.txt",
        object_key=uuid4().hex,
        storage_bucket="documents",
        detected_mime_type="text/plain",
        extension=".txt",
        file_size_bytes=10,
        checksum="a" * 64,
        processing_status="ready",
        ingestion_version=1,
        active_ingestion_version=1,
    )
    file_b = StoredFile(
        id=uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        uploaded_by=user_b.id,
        original_name="b.txt",
        object_key=uuid4().hex,
        storage_bucket="documents",
        detected_mime_type="text/plain",
        extension=".txt",
        file_size_bytes=10,
        checksum="b" * 64,
        processing_status="ready",
        ingestion_version=1,
        active_ingestion_version=1,
    )
    tenant_ids = (tenant_a.id, tenant_b.id)
    async with sessions() as session:
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all([user_a, user_b])
        await session.flush()
        session.add_all([kb_a, kb_b])
        await session.flush()
        session.add_all([file_a, file_b])
        await session.flush()
        session.add_all(
            [
                DocumentChunk(
                    tenant_id=tenant_a.id,
                    knowledge_base_id=kb_a.id,
                    file_id=file_a.id,
                    ingestion_version=1,
                    chunk_index=0,
                    content="tenant a contract",
                    content_hash="c" * 64,
                    token_count=3,
                    embedding=[1.0] * 384,
                ),
                DocumentChunk(
                    tenant_id=tenant_b.id,
                    knowledge_base_id=kb_b.id,
                    file_id=file_b.id,
                    ingestion_version=1,
                    chunk_index=0,
                    content="tenant b secret",
                    content_hash="d" * 64,
                    token_count=3,
                    embedding=[1.0] * 384,
                ),
            ]
        )
        await session.commit()
        dense = await DocumentRepository(session).dense_candidates(
            tenant_a.id, [kb_a.id], [1.0] * 384, 10
        )
        assert len(dense) == 1
        assert dense[0][0].tenant_id == tenant_a.id
        vector_extension = await session.scalar(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        )
        hnsw_index = await session.scalar(
            text(
                "SELECT count(*) FROM pg_indexes WHERE indexname = 'idx_document_chunks_embedding_hnsw'"
            )
        )
        assert vector_extension == hnsw_index == 1

        session.add(
            DocumentChunk(
                tenant_id=tenant_a.id,
                knowledge_base_id=kb_a.id,
                file_id=file_b.id,
                ingestion_version=1,
                chunk_index=7,
                content="cross tenant",
                content_hash="e" * 64,
                token_count=2,
                embedding=[0.0] * 384,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        await session.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
        await session.commit()
    await engine.dispose()
