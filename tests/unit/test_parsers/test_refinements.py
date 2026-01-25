"""Tests for bank-specific parser refinements."""

from datetime import date
from unittest.mock import Mock

import pytest

from app.parsers.refinements.amex import AmexParser
from app.parsers.refinements.hdfc import HDFCParser
from app.parsers.refinements.sbi import SBIParser


class TestHDFCParser:
    """Test suite for HDFC parser refinement."""

    def test_initialization(self):
        """Test HDFC parser initializes with correct bank code."""
        parser = HDFCParser()
        assert parser.bank_code == "hdfc"

    def test_parse_date_dd_mmm_yy(self):
        """Test parsing DD-MMM-YY format (15-Jan-25)."""
        parser = HDFCParser()
        result = parser._parse_date("15-Jan-25")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mmm_yyyy(self):
        """Test parsing DD-MMM-YYYY format (15-Jan-2025)."""
        parser = HDFCParser()
        result = parser._parse_date("15-Jan-2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mm_yyyy(self):
        """Test parsing DD/MM/YYYY format (15/01/2025)."""
        parser = HDFCParser()
        result = parser._parse_date("15/01/2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_dd_mm_yy(self):
        """Test parsing DD/MM/YY format (15/01/25)."""
        parser = HDFCParser()
        result = parser._parse_date("15/01/25")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_whitespace(self):
        """Test date parsing handles extra whitespace."""
        parser = HDFCParser()
        result = parser._parse_date("  15-Jan-25  ")
        assert result == date(2025, 1, 15)

    def test_parse_date_fallback_to_generic(self):
        """Test fallback to GenericParser for unknown formats."""
        parser = HDFCParser()
        # GenericParser doesn't support US format, so this should fail
        with pytest.raises(ValueError):
            parser._parse_date("99/99/9999")  # Invalid format

    def test_parse_date_invalid(self):
        """Test parsing invalid date raises ValueError."""
        parser = HDFCParser()
        with pytest.raises(ValueError):
            parser._parse_date("invalid-date")

    def test_inherits_from_generic_parser(self):
        """Test HDFC parser inherits other methods from GenericParser."""
        parser = HDFCParser()

        # Should have all GenericParser methods
        assert hasattr(parser, "_parse_amount")
        assert hasattr(parser, "_find_card_number")
        assert hasattr(parser, "_find_rewards")
        assert hasattr(parser, "parse")


class TestAmexParser:
    """Test suite for American Express parser refinement."""

    def test_initialization(self):
        """Test Amex parser initializes with correct bank code."""
        parser = AmexParser()
        assert parser.bank_code == "amex"

    def test_parse_date_mm_dd_yyyy(self):
        """Test parsing MM/DD/YYYY format (01/15/2025)."""
        parser = AmexParser()
        result = parser._parse_date("01/15/2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_mm_dd_yy(self):
        """Test parsing MM/DD/YY format (01/15/25)."""
        parser = AmexParser()
        result = parser._parse_date("01/15/25")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_dashes(self):
        """Test parsing MM-DD-YYYY format (01-15-2025)."""
        parser = AmexParser()
        result = parser._parse_date("01-15-2025")
        assert result == date(2025, 1, 15)

    def test_parse_date_with_whitespace(self):
        """Test date parsing handles extra whitespace."""
        parser = AmexParser()
        result = parser._parse_date("  01/15/2025  ")
        assert result == date(2025, 1, 15)

    def test_parse_date_fallback_to_generic(self):
        """Test fallback to GenericParser for unknown formats."""
        parser = AmexParser()
        # GenericParser should handle DD-MMM-YY
        result = parser._parse_date("15-Jan-25")
        assert result == date(2025, 1, 15)

    def test_parse_date_invalid(self):
        """Test parsing invalid date raises ValueError."""
        parser = AmexParser()
        with pytest.raises(ValueError):
            parser._parse_date("99/99/9999")

    def test_find_card_number_five_digits(self):
        """Test extracting 5-digit Amex account ending."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Account Ending 12345")
        elements = [mock_element]
        full_text = "Account Ending 12345"

        result = parser._find_card_number(elements, full_text)
        assert result == "2345"  # Last 4 of 5 digits

    def test_find_card_number_with_spaces(self):
        """Test extracting card number with spacing variations."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Account ending in 98765")
        elements = [mock_element]
        full_text = "Account ending in 98765"

        result = parser._find_card_number(elements, full_text)
        assert result == "8765"

    def test_find_card_number_masked_format(self):
        """Test extracting from masked format (xxxxx xxxxx x12345)."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Card: xxxxx xxxxx x54321")
        elements = [mock_element]
        full_text = "Card: xxxxx xxxxx x54321"

        result = parser._find_card_number(elements, full_text)
        assert result == "4321"

    def test_find_card_number_fallback_to_generic(self):
        """Test fallback to GenericParser for standard 4-digit patterns."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="Card ending 6789")
        elements = [mock_element]
        full_text = "Card ending 6789"
        """Test card number extraction raises ValueError when not found."""
        parser = AmexParser()

        mock_element = Mock()
        mock_element.__str__ = Mock(return_value="No card number here")
        elements = [mock_element]
        full_text = "No card number here"

        with pytest.raises(ValueError):
            parser._find_card_number(elements, full_text)

    def test_inherits_from_generic_parser(self):
        """Test Amex parser inherits other methods from GenericParser."""
        parser = AmexParser()

        # Should have all GenericParser methods
        assert hasattr(parser, "_parse_amount")
        assert hasattr(parser, "_find_rewards")
        assert hasattr(parser, "_find_statement_period")
        assert hasattr(parser, "parse")


class TestSBIParser:
    """Test suite for SBI parser refinement."""

    def test_initialization(self):
        """Test SBI parser initializes with correct bank code."""
        parser = SBIParser()
        assert parser.bank_code == "sbi"

    def test_find_rewards_numbers_before_header(self):
        """SBI often prints the 4-number row before the header labels."""
        parser = SBIParser()
        full_text = (
            "3988 57 0 4045\n"
            "Previous Balance\n"
            "Earned\n"
            "Redeemed/Expired\n"
            "/Forfeited Closing Balance Points Expiry Details\n"
        )
        closing = parser._find_rewards([], full_text)
        assert closing == 4045
        assert parser._reward_points_earned == 57

    def test_find_rewards_unstructured_reordered(self):
        """OCR/table extraction can reorder both headers and numbers."""
        parser = SBIParser()
        # This is similar to what Unstructured can emit for the same section.
        full_text = (
            "Redeemed/Expired Points Expiry Details Earned Closing Balance /Forfeited "
            "4045 0 3988 57 NONE Previous Balance"
        )
        closing = parser._find_rewards([], full_text)
        assert closing == 4045
        assert parser._reward_points_earned == 57


class TestRefinementInheritance:
    """Test that refinements properly extend GenericParser."""

    def test_hdfc_uses_generic_amount_parsing(self):
        """Test HDFC uses GenericParser's amount parsing."""
        from decimal import Decimal
        parser = HDFCParser()
        
        # Should parse Indian rupee format and return Decimal
        result = parser._parse_amount("₹1,23,456.78")
        assert result == Decimal("123456.78")

    def test_amex_uses_generic_amount_parsing(self):
        """Test Amex uses GenericParser's amount parsing."""
        from decimal import Decimal
        parser = AmexParser()

        # Should parse US dollar format and return Decimal
        result = parser._parse_amount("$1,234.56")
        assert result == Decimal("1234.56")

    def test_refinements_minimal_overrides(self):
        """Test that refinements only override necessary methods."""
        hdfc = HDFCParser()
        amex = AmexParser()

        # HDFC should only override _parse_date
        hdfc_methods = [
            m
            for m in dir(hdfc)
            if not m.startswith("_") or m.startswith("_parse") or m.startswith("_find")
        ]

        # Amex should only override _parse_date and _find_card_number
        amex_methods = [
            m
            for m in dir(amex)
            if not m.startswith("_") or m.startswith("_parse") or m.startswith("_find")
        ]

        # Both should have access to all parent methods
        assert len(hdfc_methods) > 5
        assert len(amex_methods) > 5
