"""HTTP middleware shared across all public API routes."""

import logging
from uuid import uuid4

from fastapi import Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    """Return the request correlation ID assigned by the middleware."""
    return getattr(request.state, "request_id", "unavailable")


class RequestIDMiddleware:
    """Accept or generate a request ID and attach it to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied_request_id = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = supplied_request_id or str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exception:  # noqa: BLE001 - final ASGI safety boundary
            logger.error(
                "Unhandled request error request_id=%r method=%s exception_type=%s",
                request_id,
                scope.get("method", "unknown"),
                type(exception).__name__,
            )
            if response_started:
                return
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={REQUEST_ID_HEADER: request_id},
            )
            await response(scope, receive, send)
