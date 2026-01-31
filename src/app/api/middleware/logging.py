"""Request logging middleware with PII filtering.

This module provides structured logging for all API requests with:
- Unique request IDs for tracing
- Request duration tracking
- User context (when authenticated)
- PII filtering to prevent sensitive data leaks
"""

import json
import logging
import re
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# PII patterns to filter from logs
PII_PATTERNS = [
    # Credit card numbers (any 13-19 digit sequence, with or without spaces/dashes)
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{3,7}\b'), '[CARD]'),
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    # Aadhaar numbers (12 digits, with or without spaces)
    (re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'), '[AADHAAR]'),
    # PAN card (5 letters, 4 digits, 1 letter)
    (re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'), '[PAN]'),
    # Phone numbers (international format) - be more specific to avoid false positives
    (re.compile(r'\+\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4,5}'), '[PHONE]'),
    # Names (common patterns after specific keywords)
    (re.compile(r'(?:name|customer|holder|owner)[\s:]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', re.I), r'\1 [NAME]'),
]


def filter_pii(text: str) -> str:
    """Remove PII from text using regex patterns.

    Args:
        text: Input text that may contain PII

    Returns:
        Text with PII replaced by placeholders
    """
    if not text:
        return text

    filtered = text
    for pattern, replacement in PII_PATTERNS:
        filtered = pattern.sub(replacement, filtered)

    return filtered


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with PII filtering."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Extract user ID if authenticated
        user_id = None
        if hasattr(request.state, "user"):
            user_id = getattr(request.state.user, "id", None)

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "method": request.method,
                "path": filter_pii(str(request.url.path)),
                "client_ip": request.client.host if request.client else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log error and re-raise
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "method": request.method,
                    "path": filter_pii(str(request.url.path)),
                    "duration_ms": duration_ms,
                    "error": filter_pii(str(exc)),
                },
            )
            raise

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "method": request.method,
                "path": filter_pii(str(request.url.path)),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response


class JSONLogFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": filter_pii(record.getMessage()),
        }

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id") and record.user_id:
            log_data["user_id"] = record.user_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = filter_pii(self.formatException(record.exc_info))

        # Add traceback if present
        if hasattr(record, "traceback"):
            log_data["traceback"] = filter_pii(record.traceback)

        return json.dumps(log_data)
