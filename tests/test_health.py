"""Behavior tests for the Phase 1 infrastructure endpoints."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.main import create_app


class HealthySession:
    async def execute(self, _: object) -> None:
        return None


class UnhealthySession:
    async def execute(self, _: object) -> None:
        raise SQLAlchemyError("connection details must not reach the response")


@pytest.mark.asyncio
async def test_liveness_reports_service_metadata() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Tenant Intelligence",
        "version": "1.0.0",
    }


@pytest.mark.asyncio
async def test_readiness_reports_healthy_database() -> None:
    app = create_app()

    async def healthy_session() -> AsyncIterator[AsyncSession]:
        yield HealthySession()  # type: ignore[misc]

    app.dependency_overrides[get_db_session] = healthy_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "up"},
    }


@pytest.mark.asyncio
async def test_readiness_sanitizes_database_failure() -> None:
    app = create_app()

    async def unhealthy_session() -> AsyncIterator[AsyncSession]:
        yield UnhealthySession()  # type: ignore[misc]

    app.dependency_overrides[get_db_session] = unhealthy_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "down"},
    }
    assert "connection details" not in response.text


@pytest.mark.asyncio
async def test_openapi_documents_health_endpoints() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == (
        "Tenant Intelligence"
    )
    assert schema["info"]["version"] == "1.0.0"
    assert {"/api/health/live", "/api/health/ready"}.issubset(schema["paths"])
    assert {
        "/api/database-connections",
        "/api/database-connections/{connection_id}",
        "/api/database-connections/{connection_id}/test",
        "/api/database-connections/{connection_id}/sync-schema",
        "/api/database-connections/{connection_id}/schemas",
        "/api/database-connections/{connection_id}/tables",
    }.issubset(schema["paths"])


@pytest.mark.asyncio
async def test_unknown_route_returns_404() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/unknown-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_path", ["/health", "/health/ready"])
async def test_legacy_health_routes_are_not_exposed(legacy_path: str) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(legacy_path)

    assert response.status_code == 404
