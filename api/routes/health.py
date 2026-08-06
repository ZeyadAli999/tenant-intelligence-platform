"""Infrastructure liveness and readiness endpoints."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db_session
from app.middleware import get_request_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessChecks(BaseModel):
    database: Literal["up", "down"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def liveness() -> LivenessResponse:
    """Confirm that the API process can serve requests without touching dependencies."""
    settings = get_settings()
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "The database dependency is unavailable.",
        }
    },
    summary="Readiness probe",
)
async def readiness(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadinessResponse | JSONResponse:
    """Confirm that PostgreSQL accepts a minimal query."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning(
            "Database readiness check failed request_id=%r",
            get_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": {"database": "down"}},
        )

    return ReadinessResponse(status="ready", checks=ReadinessChecks(database="up"))
