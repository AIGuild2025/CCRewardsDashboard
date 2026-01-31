"""Error codes and user-friendly messages.

This module defines the error catalog for statement processing.
Each error has:
- error_code: Unique identifier
- message: Technical description (for logs)
- user_message: User-friendly explanation
- suggestion: Actionable guidance for the user
- retry_allowed: Whether the error is retryable
"""

from dataclasses import dataclass


@dataclass
class ErrorDefinition:
    """Definition of a single error type."""

    code: str
    message: str
    user_message: str
    suggestion: str
    retry_allowed: bool


# Error catalog for statement processing
ERROR_CATALOG: dict[str, dict] = {
    "PARSE_001": {
        "code": "PARSE_001",
        "message": "Unsupported bank format detected",
        "user_message": "We couldn't recognize this statement format.",
        "suggestion": "Please upload a statement from HDFC, ICICI, SBI, Amex, Citi, or Chase.",
        "retry_allowed": False,
    },
    "PARSE_002": {
        "code": "PARSE_002",
        "message": "PDF extraction failed: corrupted or invalid file",
        "user_message": "This PDF appears to be corrupted or damaged.",
        "suggestion": "Try downloading the statement again from your bank's website.",
        "retry_allowed": True,
    },
    "PARSE_003": {
        "code": "PARSE_003",
        "message": "PDF is password-protected",
        "user_message": "This statement requires a password.",
        "suggestion": "Please provide the PDF password and try again.",
        "retry_allowed": True,
    },
    "PARSE_004": {
        "code": "PARSE_004",
        "message": "Incorrect password provided for encrypted PDF",
        "user_message": "The password you provided is incorrect.",
        "suggestion": "Check your password and try again.",
        "retry_allowed": True,
    },
    "PARSE_005": {
        "code": "PARSE_005",
        "message": "Could not extract required transaction data from statement",
        "user_message": "We couldn't extract transactions from this statement.",
        "suggestion": "The statement format may have changed. Please contact support if this persists.",
        "retry_allowed": False,
    },
    "MASK_001": {
        "code": "MASK_001",
        "message": "PII masking failed to complete",
        "user_message": "We encountered an error while processing your statement.",
        "suggestion": "Please try again. Contact support if the problem persists.",
        "retry_allowed": True,
    },
    "MASK_002": {
        "code": "MASK_002",
        "message": "PII validation failed: sensitive data detected after masking",
        "user_message": "We encountered a security issue while processing your statement.",
        "suggestion": "Please contact support. Your data has not been stored.",
        "retry_allowed": False,
    },
    "DB_001": {
        "code": "DB_001",
        "message": "Database transaction failed during statement persistence",
        "user_message": "We couldn't save your statement due to a database error.",
        "suggestion": "Please try again in a few moments.",
        "retry_allowed": True,
    },
    "VAL_001": {
        "code": "VAL_001",
        "message": "Parsed statement data failed validation",
        "user_message": "The statement data appears to be incomplete or invalid.",
        "suggestion": "Please ensure you're uploading a complete bank statement PDF.",
        "retry_allowed": False,
    },
    # API-specific errors
    "API_001": {
        "code": "API_001",
        "message": "Invalid file type uploaded",
        "user_message": "Only PDF files are supported.",
        "suggestion": "Please upload a PDF file. Most banks provide statements in PDF format.",
        "retry_allowed": False,
    },
    "API_002": {
        "code": "API_002",
        "message": "File size exceeds maximum limit",
        "user_message": "The file is too large. Maximum file size is 25 MB.",
        "suggestion": "Please upload a smaller statement file (max 25 MB).",
        "retry_allowed": False,
    },
    "API_003": {
        "code": "API_003",
        "message": "Statement not found",
        "user_message": "We couldn't find this statement.",
        "suggestion": "Please check the statement ID and try again.",
        "retry_allowed": False,
    },
    "API_004": {
        "code": "API_004",
        "message": "Access denied: statement belongs to different user",
        "user_message": "You don't have permission to access this statement.",
        "suggestion": "You can only access your own statements.",
        "retry_allowed": False,
    },
    "API_005": {
        "code": "API_005",
        "message": "Invalid PDF magic bytes",
        "user_message": "This file appears to be corrupt or is not a valid PDF.",
        "suggestion": "Please ensure you're uploading an actual PDF file, not a renamed file.",
        "retry_allowed": False,
    },
    "API_006": {
        "code": "API_006",
        "message": "Transaction not found",
        "user_message": "We couldn't find this transaction.",
        "suggestion": "Please refresh and try again.",
        "retry_allowed": False,
    },
    "API_007": {
        "code": "API_007",
        "message": "Invalid category",
        "user_message": "That category isn't supported.",
        "suggestion": "Please choose a category from the allowed list.",
        "retry_allowed": False,
    },
    "API_008": {
        "code": "API_008",
        "message": "Category override not allowed for credit transactions",
        "user_message": "You can only recategorize debit (spend) transactions.",
        "suggestion": "Choose a debit transaction instead of a payment/refund.",
        "retry_allowed": False,
    },
    "API_009": {
        "code": "API_009",
        "message": "Transaction merchant is missing",
        "user_message": "We couldn't determine the merchant for this transaction.",
        "suggestion": "Please choose a different transaction.",
        "retry_allowed": False,
    },
}


def get_error(error_code: str) -> dict:
    """Get error definition by code.

    Args:
        error_code: Error code from the catalog

    Returns:
        Dict with error details

    Raises:
        KeyError: If error code not found in catalog
    """
    if error_code not in ERROR_CATALOG:
        # Return a generic error if code not found
        return {
            "code": "UNKNOWN",
            "message": f"Unknown error code: {error_code}",
            "user_message": "An unexpected error occurred.",
            "suggestion": "Please try again. Contact support if the problem persists.",
            "retry_allowed": True,
        }
    return ERROR_CATALOG[error_code]


def get_user_message(error_code: str) -> str:
    """Get user-friendly message for an error code.

    Args:
        error_code: Error code from the catalog

    Returns:
        User-friendly error message
    """
    return get_error(error_code)["user_message"]


def get_suggestion(error_code: str) -> str:
    """Get actionable suggestion for an error code.

    Args:
        error_code: Error code from the catalog

    Returns:
        Suggestion text for the user
    """
    return get_error(error_code)["suggestion"]


def is_retryable(error_code: str) -> bool:
    """Check if an error is retryable.

    Args:
        error_code: Error code from the catalog

    Returns:
        True if the operation can be retried, False otherwise
    """
    return get_error(error_code)["retry_allowed"]
