"""Unit tests for error handling middleware and PII filtering."""

import logging
import re
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.middleware.error_handler import (
    handle_generic_error,
    handle_integrity_error,
    handle_statement_processing_error,
    handle_validation_error,
)
from app.api.middleware.logging import filter_pii
from app.core.exceptions import StatementProcessingError


class TestStatementProcessingErrorHandler:
    """Test custom exception handling."""

    @pytest.mark.asyncio
    async def test_handle_statement_processing_error(self):
        """Test handling of StatementProcessingError."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/statements/upload"
        request.method = "POST"

        exc = StatementProcessingError(
            error_code="PARSE_001",
            details={"bank": "unknown"},
            http_status=400,
        )

        response = await handle_statement_processing_error(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        content = response.body.decode()
        assert "PARSE_001" in content
        assert "error_code" in content

    @pytest.mark.asyncio
    async def test_error_includes_all_fields(self):
        """Test error response includes all required fields."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"

        exc = StatementProcessingError(error_code="API_003", http_status=404)

        response = await handle_statement_processing_error(request, exc)
        
        import json
        content = json.loads(response.body.decode())
        
        assert "error_code" in content
        assert "message" in content
        assert "user_message" in content
        assert "suggestion" in content
        assert "retry_allowed" in content


class TestValidationErrorHandler:
    """Test validation error handling."""

    @pytest.mark.asyncio
    async def test_handle_validation_error(self):
        """Test handling of RequestValidationError."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/statements"
        request.method = "GET"

        # Create a mock validation error
        exc = RequestValidationError(
            errors=[
                {
                    "loc": ("query", "limit"),
                    "msg": "value must be <= 100",
                    "type": "value_error",
                }
            ]
        )

        response = await handle_validation_error(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "VAL_001"
        assert "limit" in content["message"]

    @pytest.mark.asyncio
    async def test_validation_error_multiple_fields(self):
        """Test validation error with multiple field errors."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "POST"

        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error"},
                {"loc": ("body", "password"), "msg": "too short", "type": "value_error"},
            ]
        )

        response = await handle_validation_error(request, exc)
        
        import json
        content = json.loads(response.body.decode())
        
        assert "email" in content["message"]
        assert "password" in content["message"]


class TestIntegrityErrorHandler:
    """Test database integrity error handling."""

    @pytest.mark.asyncio
    async def test_handle_duplicate_key_error(self):
        """Test handling of duplicate key database error."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/statements"
        request.method = "POST"

        # Mock integrity error with duplicate key
        exc = IntegrityError("statement", "params", "UNIQUE constraint failed")

        response = await handle_integrity_error(request, exc)

        assert response.status_code == 409
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "DB_002"

    @pytest.mark.asyncio
    async def test_handle_generic_db_error(self):
        """Test handling of generic database error."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "POST"

        exc = IntegrityError("statement", "params", "Foreign key constraint failed")

        response = await handle_integrity_error(request, exc)

        assert response.status_code == 500
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "DB_001"


class TestGenericErrorHandler:
    """Test generic exception handling."""

    @pytest.mark.asyncio
    async def test_handle_generic_error(self):
        """Test handling of unexpected exceptions."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"

        exc = Exception("Something went wrong")

        response = await handle_generic_error(request, exc)

        assert response.status_code == 500
        
        import json
        content = json.loads(response.body.decode())
        
        assert content["error_code"] == "SYS_001"
        assert content["user_message"] == "An unexpected error occurred"
        # Should not expose internal error details
        assert "Something went wrong" not in content["user_message"]


class TestPIIFiltering:
    """Test PII filtering functionality."""

    def test_filter_credit_card(self):
        """Test filtering of credit card numbers."""
        text = "Card number 4532015112830366 was used"
        filtered = filter_pii(text)
        assert "4532015112830366" not in filtered
        assert "[CARD]" in filtered

    def test_filter_email(self):
        """Test filtering of email addresses."""
        text = "Contact john.doe@example.com for help"
        filtered = filter_pii(text)
        assert "john.doe@example.com" not in filtered
        assert "[EMAIL]" in filtered

    def test_filter_phone_number(self):
        """Test filtering of phone numbers."""
        text = "Call us at +1-555-123-4567"
        filtered = filter_pii(text)
        assert "555-123-4567" not in filtered
        assert "[PHONE]" in filtered

    def test_filter_aadhaar(self):
        """Test filtering of Aadhaar numbers."""
        text = "Aadhaar: 2345 6789 0123"
        filtered = filter_pii(text)
        assert "2345 6789 0123" not in filtered
        assert "[AADHAAR]" in filtered

    def test_filter_pan_card(self):
        """Test filtering of PAN card numbers."""
        text = "PAN: ABCDE1234F"
        filtered = filter_pii(text)
        assert "ABCDE1234F" not in filtered
        assert "[PAN]" in filtered

    def test_filter_multiple_pii(self):
        """Test filtering multiple PII types in same text."""
        text = "Card 4532015112830366, email test@example.com, phone +91-98765-43210"
        filtered = filter_pii(text)
        
        assert "4532015112830366" not in filtered
        assert "test@example.com" not in filtered
        assert "98765-43210" not in filtered
        assert "[CARD]" in filtered
        assert "[EMAIL]" in filtered
        assert "[PHONE]" in filtered

    def test_filter_preserves_non_pii(self):
        """Test that non-PII text is preserved."""
        text = "Transaction for $50.00 at Starbucks"
        filtered = filter_pii(text)
        assert filtered == text

    def test_filter_empty_string(self):
        """Test filtering empty string."""
        assert filter_pii("") == ""

    def test_filter_none(self):
        """Test filtering None value."""
        assert filter_pii(None) is None


class TestErrorResponseFormat:
    """Test error response structure."""

    @pytest.mark.asyncio
    async def test_error_response_has_required_fields(self):
        """Test all error responses have required fields."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"

        exc = StatementProcessingError(error_code="API_001", http_status=400)
        response = await handle_statement_processing_error(request, exc)

        import json
        content = json.loads(response.body.decode())

        # Check all required fields present
        required_fields = ["error_code", "message", "user_message", "suggestion", "retry_allowed"]
        for field in required_fields:
            assert field in content, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_4xx_errors_have_suggestions(self):
        """Test 4xx errors include actionable suggestions."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "POST"

        exc = StatementProcessingError(error_code="API_001", http_status=400)
        response = await handle_statement_processing_error(request, exc)

        import json
        content = json.loads(response.body.decode())

        assert len(content["suggestion"]) > 0
        assert content["suggestion"] != ""

    @pytest.mark.asyncio
    async def test_5xx_errors_dont_expose_internals(self):
        """Test 5xx errors don't expose internal details."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "GET"

        exc = Exception("Database connection failed: host=localhost port=5432")
        response = await handle_generic_error(request, exc)

        import json
        content = json.loads(response.body.decode())

        # Should not expose internal error message
        assert "Database connection failed" not in content["user_message"]
        assert "localhost" not in content["user_message"]
        assert "5432" not in content["user_message"]


class TestLoggingBehavior:
    """Test logging behavior of error handlers."""

    @pytest.mark.asyncio
    async def test_errors_are_logged(self, caplog):
        """Test that errors are logged with context."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/statements"
        request.method = "POST"

        exc = StatementProcessingError(
            error_code="PARSE_001",
            details={"bank": "unknown"},
            http_status=400,
        )

        with caplog.at_level(logging.ERROR):
            await handle_statement_processing_error(request, exc)

        # Check error was logged
        assert len(caplog.records) > 0
        assert "PARSE_001" in caplog.text

    @pytest.mark.asyncio
    async def test_validation_errors_logged_as_warning(self, caplog):
        """Test validation errors logged at WARNING level."""
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.method = "POST"

        exc = RequestValidationError(
            errors=[{"loc": ("body", "email"), "msg": "invalid", "type": "value_error"}]
        )

        with caplog.at_level(logging.WARNING):
            await handle_validation_error(request, exc)

        assert len(caplog.records) > 0
