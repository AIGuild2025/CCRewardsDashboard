"""Custom exception classes for statement processing.

This module defines a hierarchy of exceptions used throughout the
statement processing pipeline. Each exception maps to a specific
error code defined in errors.py.
"""

from typing import Any


class StatementProcessingError(Exception):
    """Base exception for all statement processing errors.

    All custom exceptions inherit from this base class and include
    an error_code that maps to the error catalog.

    Attributes:
        error_code: Code from the error catalog (e.g., "PARSE_001")
        details: Additional context about the error (for logging)
        http_status: HTTP status code to return (default: 500)
    """

    def __init__(
        self,
        error_code: str,
        details: dict[str, Any] | None = None,
        http_status: int = 500,
    ):
        """Initialize the exception.

        Args:
            error_code: Error code from errors.py
            details: Additional error context (not shown to users)
            http_status: HTTP status code (default: 500)
        """
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status
        super().__init__(error_code)


class PDFExtractionError(StatementProcessingError):
    """Raised when PDF extraction fails.

    Common causes:
    - Corrupted PDF file (PARSE_002)
    - Password-protected PDF (PARSE_003)
    - Incorrect password (PARSE_004)
    - Invalid file format
    """

    pass


class BankDetectionError(StatementProcessingError):
    """Raised when bank cannot be detected from PDF content.

    This typically indicates an unsupported bank or statement format.
    Maps to error code PARSE_001.
    """

    pass


class ParsingError(StatementProcessingError):
    """Raised when statement parsing fails.

    Common causes:
    - Required fields missing (PARSE_005)
    - Unexpected statement format
    - Data validation failures
    """

    pass


class MaskingError(StatementProcessingError):
    """Raised when PII masking fails or validation detects leaks.

    This is a critical error that prevents data persistence.
    Should never happen in production if masking pipeline is working.
    """

    pass


class ValidationError(StatementProcessingError):
    """Raised when parsed data fails validation.

    This includes:
    - Missing required fields
    - Invalid data types
    - Business rule violations
    """

    pass
