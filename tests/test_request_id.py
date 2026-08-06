"""Request correlation and sanitized failure behavior tests."""

from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from app.main import create_app
from app.middleware import REQUEST_ID_HEADER


@pytest.mark.asyncio
async def test_supplied_request_id_is_returned_unchanged() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/health/live",
            headers={REQUEST_ID_HEADER: "client-request-123"},
        )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "client-request-123"


@pytest.mark.asyncio
async def test_missing_request_id_generates_uuid() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/unknown-route")

    generated_request_id = response.headers[REQUEST_ID_HEADER]
    parsed_request_id = UUID(generated_request_id)
    assert response.status_code == 404
    assert str(parsed_request_id) == generated_request_id
    assert parsed_request_id.version == 4


@pytest.mark.asyncio
async def test_unhandled_error_is_correlated_and_sanitized() -> None:
    app = create_app()
    secret_exception_detail = (
        "DATABASE_URL=postgresql+asyncpg://admin:password@database/private"
    )

    @app.get("/api/test-only/error", include_in_schema=False)
    async def raise_test_error() -> None:
        raise RuntimeError(secret_exception_detail)

    request_id = "error-request-456"
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    with patch("app.middleware.logger.error") as error_log:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/test-only/error",
                headers={REQUEST_ID_HEADER: request_id},
            )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert secret_exception_detail not in response.text

    error_log.assert_called_once()
    logged_call = repr(error_log.call_args)
    assert request_id in logged_call
    assert secret_exception_detail not in logged_call
    assert "password" not in logged_call.lower()
