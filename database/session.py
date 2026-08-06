"""Async SQLAlchemy engine and request-scoped session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    hide_parameters=True,
    pool_pre_ping=True,
)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield one SQLAlchemy session for the duration of a request."""
    async with AsyncSessionFactory() as session:
        yield session


async def dispose_engine() -> None:
    """Close pooled database connections during application shutdown."""
    await engine.dispose()
