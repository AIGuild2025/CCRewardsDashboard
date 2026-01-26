"""Global error handling middleware.

This module provides consistent error responses across all API endpoints.
All exceptions are caught and converted to a standardized JSON format with
appropriate HTTP status codes.
"""

import logging
from typing import Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.errors import ERROR_CATALOG
from app.core.exceptions import StatementProcessingError

logger = logging.getLogger(__name__)


async def handle_statement_processing_error(
    request: Request, exc: StatementProcessingError
) -> JSONResponse:
    """Handle custom statement processing exceptions.

    Args:
        request: The incoming request
        exc: The statement processing exception

    Returns:
        JSONResponse with error details from catalog
    """
    # Get error details from catalog
    error_info = ERROR_CATALOG.get(exc.error_code, {})

    # Avoid logging exception details in non-debug to reduce risk of leaking
    # sensitive content (e.g., parser error messages).
    extra = {"error_code": exc.error_code, "path": request.url.path, "method": request.method}
    if settings.debug:
        extra["details"] = exc.details

    logger.error(f"Statement processing error: {exc.error_code}", extra=extra)

    # Return consistent error response
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error_code": exc.error_code,
            "message": error_info.get("message", str(exc)),
            "user_message": error_info.get("user_message", "An error occurred"),
            "suggestion": error_info.get("suggestion", "Please try again later"),
            "retry_allowed": error_info.get("retry_allowed", False),
        },
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: The incoming request
        exc: The validation error

    Returns:
        JSONResponse with validation error details
    """
    # Extract field-level errors
    errors = exc.errors()
    error_messages = []

    for error in errors:
        field = ".".join(str(x) for x in error.get("loc", []))
        msg = error.get("msg", "Invalid value")
        error_messages.append(f"{field}: {msg}")

    extra = {"path": request.url.path, "method": request.method}
    if settings.debug:
        extra["errors"] = errors
    logger.warning(f"Validation error on {request.url.path}", extra=extra)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "VAL_001",
            "message": " | ".join(error_messages),
            "user_message": "Invalid input data",
            "suggestion": "Please check your input and try again",
            "retry_allowed": True,
        },
    )


async def handle_integrity_error(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """Handle database integrity errors.

    Args:
        request: The incoming request
        exc: The integrity error

    Returns:
        JSONResponse with error details
    """
    # Do not log str(exc): it can include SQL + bound parameters.
    if settings.debug:
        logger.exception(
            f"Database integrity error on {request.url.path}",
            extra={"path": request.url.path, "method": request.method},
        )
    else:
        logger.error(
            f"Database integrity error on {request.url.path}",
            extra={"path": request.url.path, "method": request.method},
        )

    # Check if it's a duplicate key error
    error_msg = str(exc).lower()
    if "unique" in error_msg or "duplicate" in error_msg:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error_code": "DB_002",
                "message": "Resource already exists",
                "user_message": "This record already exists",
                "suggestion": "Please check if the record was already created",
                "retry_allowed": False,
            },
        )

    # Generic database error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "DB_001",
            "message": "Database operation failed",
            "user_message": "A database error occurred",
            "suggestion": "Please try again later",
            "retry_allowed": True,
        },
    )


async def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: The incoming request
        exc: The unexpected exception

    Returns:
        JSONResponse with generic error message
    """
    # In non-debug: do not log str(exc) or traceback (may include sensitive data).
    if settings.debug:
        logger.exception(
            f"Unexpected error on {request.url.path}",
            extra={
                "error_type": type(exc).__name__,
                "path": request.url.path,
                "method": request.method,
            },
        )
    else:
        logger.error(
            f"Unexpected error on {request.url.path}",
            extra={
                "error_type": type(exc).__name__,
                "path": request.url.path,
                "method": request.method,
            },
        )

    # Return generic error (don't expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "SYS_001",
            "message": "Internal server error",
            "user_message": "An unexpected error occurred",
            "suggestion": "Please try again later or contact support",
            "retry_allowed": True,
        },
    )
