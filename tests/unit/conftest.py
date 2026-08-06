"""Isolated async database and API fixtures for Phase 2 tests."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import models  # noqa: F401
from api.routes.chat import get_embedding_service, get_llm_provider
from app.dependencies import get_db_session
from app.main import create_app
from database.base import Base
from services.llm.fake_provider import FakeLLMProvider


class FakeEmbeddingService:
    """Deterministic 384-dimensional test double; never downloads a model."""

    model_name = "test-only-embedding"
    dimension = 384

    def embed(self, texts):
        return [
            [float((sum(text.encode()) % 31) + 1) / 32.0] * self.dimension
            for text in texts
        ]


@dataclass(frozen=True)
class DatabaseHarness:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def test_database() -> AsyncIterator[DatabaseHarness]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield DatabaseHarness(engine=engine, sessions=sessions)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(
    test_database: DatabaseHarness,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with test_database.sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
