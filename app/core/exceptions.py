"""
Custom exception hierarchy + FastAPI exception handlers.

Design principles:
- All domain errors inherit from AppException.
- Each exception carries an HTTP status, error code, and safe message.
- Handlers convert exceptions into consistent JSON responses.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------
class AppException(Exception):
    """Base class for all domain exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(AppException):
    status_code = 422
    error_code = "validation_error"
    message = "Request validation failed."


class LLMServiceException(AppException):
    """Raised when the upstream LLM provider fails or rate-limits."""
    status_code = 502
    error_code = "llm_service_error"
    message = "Upstream AI service failed."


class RiskAssessmentException(AppException):
    """Raised when risk assessment pipeline fails."""
    status_code = 500
    error_code = "risk_assessment_failed"
    message = "Risk assessment could not be completed."


class ConfigurationException(AppException):
    status_code = 500
    error_code = "configuration_error"
    message = "Service is misconfigured."


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------
def _error_payload(
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        }
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    logger.warning(
        "app_exception",
        path=request.url.path,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.error_code, exc.message, exc.details),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    logger.info(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("http_error", str(exc.detail)),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.info(
        "validation_exception",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "validation_error",
            "Request validation failed.",
            {"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            "internal_error",
            "An unexpected error occurred.",
        ),
    )


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
def register_exception_handlers(app: FastAPI) -> None:
    """Call this from app.main during FastAPI app setup."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)