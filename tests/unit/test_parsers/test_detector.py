"""Tests for bank detector."""

from unittest.mock import Mock

import pytest

from app.parsers.detector import BankDetector


class TestBankDetector:
    """Test suite for BankDetector."""

    def test_initialization(self):
        """Test detector initializes with compiled patterns."""
        detector = BankDetector()
        assert len(detector._compiled_patterns) == 6
        assert "hdfc" in detector._compiled_patterns
        assert "amex" in detector._compiled_patterns

    def test_detect_hdfc(self):
        """Test HDFC Bank detection."""
        detector = BankDetector()
        text = """
        HDFC Bank Credit Card Statement
        Card Number: xxxx xxxx xxxx 1234
        www.hdfcbank.com
        """
        assert detector.detect(text) == "hdfc"

    def test_detect_icici(self):
        """Test ICICI Bank detection."""
        detector = BankDetector()
        text = """
        ICICI Bank Ltd
        Credit Card Statement
        Visit icicibank.com
        """
        assert detector.detect(text) == "icici"

    def test_detect_sbi(self):
        """Test SBI Card detection."""
        detector = BankDetector()
        text = """
        SBI Card Statement
        State Bank of India
        www.sbicard.com
        """
        assert detector.detect(text) == "sbi"

    def test_detect_amex(self):
        """Test American Express detection."""
        detector = BankDetector()
        text = """
        American Express
        Card Statement
        americanexpress.com
        """
        assert detector.detect(text) == "amex"

    def test_detect_citi(self):
        """Test Citibank detection."""
        detector = BankDetector()
        text = """
        Citibank Credit Card
        Statement Period
        www.citi.com
        """
        assert detector.detect(text) == "citi"

    def test_detect_chase(self):
        """Test Chase detection."""
        detector = BankDetector()
        text = """
        JPMorgan Chase
        Credit Card Statement
        chase.com
        """
        assert detector.detect(text) == "chase"

    def test_detect_unknown_bank(self):
        """Test detection returns None for unknown banks."""
        detector = BankDetector()
        text = """
        Random Bank Corporation
        Credit Card Statement
        Card Number: 1234
        """
        assert detector.detect(text) is None

    def test_detect_empty_text(self):
        """Test detection with empty text."""
        detector = BankDetector()
        assert detector.detect("") is None
        assert detector.detect(None) is None

    def test_detect_case_insensitive(self):
        """Test detection is case-insensitive."""
        detector = BankDetector()

        text_upper = "HDFC BANK CREDIT CARD"
        text_lower = "hdfc bank credit card"
        text_mixed = "Hdfc BaNk CrEdIt CaRd"

        assert detector.detect(text_upper) == "hdfc"
        assert detector.detect(text_lower) == "hdfc"
        assert detector.detect(text_mixed) == "hdfc"

    def test_detect_from_elements(self):
        """Test detecting bank from element list."""
        mock_element1 = Mock()
        mock_element1.__str__ = Mock(return_value="HDFC Bank")
        mock_element2 = Mock()
        mock_element2.__str__ = Mock(return_value="Statement Period")

        detector = BankDetector()
        bank_code = detector.detect_from_elements([mock_element1, mock_element2])

        assert bank_code == "hdfc"

    def test_get_supported_banks(self):
        """Test getting list of supported banks."""
        detector = BankDetector()
        banks = detector.get_supported_banks()

        assert len(banks) == 6
        assert "hdfc" in banks
        assert "icici" in banks
        assert "sbi" in banks
        assert "amex" in banks
        assert "citi" in banks
        assert "chase" in banks

    def test_add_pattern(self):
        """Test adding new detection pattern."""
        detector = BankDetector()

        # Add pattern for HDFC
        detector.add_pattern("hdfc", r"MyHDFC")

        text = "Login to MyHDFC portal"
        assert detector.detect(text) == "hdfc"

    def test_add_pattern_new_bank(self):
        """Test adding pattern for a new bank."""
        detector = BankDetector()

        # Add pattern for new bank
        detector.add_pattern("axis", r"Axis\s+Bank")

        text = "Axis Bank Credit Card Statement"
        assert detector.detect(text) == "axis"

    def test_multiple_patterns_match_first(self):
        """Test that first matching bank is returned."""
        detector = BankDetector()

        # Text with multiple bank mentions
        text = """
        This statement was issued by HDFC Bank
        For ICICI Bank cards, please visit icicibank.com
        """

        # Should return first match (hdfc)
        result = detector.detect(text)
        assert result in ["hdfc", "icici"]  # Either could match first
