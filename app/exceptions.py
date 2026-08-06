"""Application-wide exception handling."""

import logging
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.middleware import REQUEST_ID_HEADER, get_request_id

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    status_code = 400
    detail = "Invalid request"
    headers: ClassVar[dict[str, str] | None] = None
    code: str | None = None


class AuthenticationError(ApplicationError):
    status_code = 401
    detail = "Invalid credentials"
    headers: ClassVar[dict[str, str]] = {"WWW-Authenticate": "Bearer"}


class AuthorizationError(ApplicationError):
    status_code = 403
    detail = "Insufficient permissions"


class AdministratorRequiredError(AuthorizationError):
    detail = "Administrator access required"
    code = "ADMINISTRATOR_REQUIRED"


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(ApplicationError):
    status_code = 409
    detail = "Resource already exists"


class FinalAdministratorError(ConflictError):
    detail = "At least one active Administrator must remain"
    code = "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED"


class UnsupportedDatabaseTypeError(ApplicationError):
    status_code = 400
    detail = "Unsupported database type"


class InvalidDatabaseHostError(ApplicationError):
    status_code = 400
    detail = "Invalid database host"


class ConnectionNotReadyError(ApplicationError):
    status_code = 400
    detail = "Database connection is not ready"


class InvalidPermissionError(ApplicationError):
    status_code = 400
    detail = "Invalid permission"


class InvalidDocumentError(ApplicationError):
    detail = "Invalid document"

    def __init__(self, code: str) -> None:
        self.code = code


def register_exception_handlers(app: FastAPI) -> None:
    """Return a stable error contract without leaking internal exception details."""

    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        _: Request,
        exception: ApplicationError,
    ) -> JSONResponse:
        content = {"detail": exception.detail}
        if exception.code:
            content["code"] = exception.code
        return JSONResponse(
            status_code=exception.status_code,
            content=content,
            headers=exception.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request,
        __: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid request"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exception: Exception
    ) -> JSONResponse:
        request_id = get_request_id(request)
        logger.error(
            "Unhandled request error request_id=%r method=%s exception_type=%s",
            request_id,
            request.method,
            type(exception).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers={REQUEST_ID_HEADER: request_id},
        )
