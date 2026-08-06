"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router import api_router
from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging
from app.middleware import RequestIDMiddleware
from database.session import dispose_engine
from services.llm.factory import build_llm_provider


def create_app() -> FastAPI:
    """Build the FastAPI application with explicit startup and shutdown behavior."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        description=(
            "Phase 4 tenant-isolated database, document, and hybrid chat with "
            "validated read-only SQL, local embeddings, grounded citations, "
            "masked results, auditable conversations, and SSE streaming."
        ),
    )
    # A production application has exactly one provider: Groq. Tests replace the
    # dependency explicitly; startup never selects or falls back to a test double.
    application.state.llm_provider = build_llm_provider(settings)
    application.add_middleware(RequestIDMiddleware)
    application.include_router(api_router, prefix=settings.api_prefix)
    register_exception_handlers(application)
    return application


app = create_app()
