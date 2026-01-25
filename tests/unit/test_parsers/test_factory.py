"""Tests for parser factory."""

from unittest.mock import Mock, patch

import pytest

from app.parsers.detector import BankDetector
from app.parsers.extractor import PDFExtractor
from app.parsers.factory import ParserFactory, get_parser_factory, parse_statement
from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedStatement


class CustomParser(GenericParser):
    """Custom parser for testing refinements."""

    pass


class TestParserFactory:
    """Test suite for ParserFactory."""

    def test_initialization_default(self):
        """Test factory initializes with default components."""
        factory = ParserFactory()

        assert isinstance(factory.extractor, PDFExtractor)
        assert isinstance(factory.detector, BankDetector)
        assert factory._refinements == {}

    def test_initialization_custom_components(self):
        """Test factory with custom extractor and detector."""
        custom_extractor = PDFExtractor(strategy="hi_res")
        custom_detector = BankDetector()

        factory = ParserFactory(
            extractor=custom_extractor, detector=custom_detector
        )

        assert factory.extractor is custom_extractor
        assert factory.detector is custom_detector

    @patch.object(PDFExtractor, "extract")
    @patch.object(BankDetector, "detect_from_elements")
    @patch.object(GenericParser, "parse")
    def test_parse_unknown_bank(self, mock_parse, mock_detect, mock_extract):
        """Test parsing with unknown bank uses GenericParser."""
        # Setup mocks
        mock_element = Mock()
        mock_extract.return_value = [mock_element]
        mock_detect.return_value = None  # Unknown bank

        mock_statement = ParsedStatement(
            card_last_four="1234",
            statement_month="2025-01-01",
            closing_balance_cents=100000,
        )
        mock_parse.return_value = mock_statement

        # Test
        factory = ParserFactory()
        pdf_bytes = b"fake pdf"
        result = factory.parse(pdf_bytes)

        # Verify
        assert result == mock_statement
        mock_extract.assert_called_once_with(pdf_bytes, password=None)
        mock_detect.assert_called_once_with([mock_element])
        mock_parse.assert_called_once()

    @patch.object(PDFExtractor, "extract")
    @patch.object(BankDetector, "detect_from_elements")
    def test_parse_known_bank_without_refinement(self, mock_detect, mock_extract):
        """Test parsing known bank without registered refinement."""
        mock_element = Mock()
        mock_element.__str__ = Mock(
            return_value="""
            Card Number: xxxx 1234
            Statement Period: 01-Jan-25 to 31-Jan-25
            Closing Balance: 10000.00
            """
        )
        mock_extract.return_value = [mock_element]
        mock_detect.return_value = "hdfc"

        factory = ParserFactory()
        result = factory.parse(b"fake pdf")

        # Should use GenericParser even though bank is known
        assert isinstance(result, ParsedStatement)
        assert result.bank_code == "hdfc"

    @patch.object(PDFExtractor, "extract")
    @patch.object(BankDetector, "detect_from_elements")
    def test_parse_with_refinement(self, mock_detect, mock_extract):
        """Test parsing uses registered refinement."""
        mock_element = Mock()
        mock_element.__str__ = Mock(
            return_value="""
            Card Number: xxxx 1234
            Statement Period: 01-Jan-25 to 31-Jan-25
            Closing Balance: 10000.00
            """
        )
        mock_extract.return_value = [mock_element]
        mock_detect.return_value = "hdfc"

        # Register custom parser
        factory = ParserFactory()
        factory.register_refinement("hdfc", CustomParser)

        result = factory.parse(b"fake pdf")

        # Verify refinement was used
        assert isinstance(result, ParsedStatement)
        assert result.bank_code == "hdfc"

    def test_register_refinement_valid(self):
        """Test registering a valid refinement."""
        factory = ParserFactory()
        factory.register_refinement("hdfc", CustomParser)

        assert "hdfc" in factory._refinements
        assert factory._refinements["hdfc"] == CustomParser

    def test_register_refinement_invalid(self):
        """Test registering invalid refinement raises error."""
        factory = ParserFactory()

        class NotAParser:
            pass

        with pytest.raises(ValueError, match="must inherit from GenericParser"):
            factory.register_refinement("hdfc", NotAParser)

    def test_unregister_refinement(self):
        """Test unregistering a refinement."""
        factory = ParserFactory()
        factory.register_refinement("hdfc", CustomParser)

        assert "hdfc" in factory._refinements

        factory.unregister_refinement("hdfc")
        assert "hdfc" not in factory._refinements

    def test_unregister_nonexistent_refinement(self):
        """Test unregistering non-existent refinement doesn't error."""
        factory = ParserFactory()
        factory.unregister_refinement("nonexistent")  # Should not raise

    def test_get_registered_banks(self):
        """Test getting list of registered banks."""
        factory = ParserFactory()
        factory.register_refinement("hdfc", CustomParser)
        factory.register_refinement("amex", CustomParser)

        banks = factory.get_registered_banks()

        assert len(banks) == 2
        assert "hdfc" in banks
        assert "amex" in banks

    def test_get_registered_banks_empty(self):
        """Test getting registered banks when none exist."""
        factory = ParserFactory()
        banks = factory.get_registered_banks()
        assert banks == []

    def test_get_parser_class_with_refinement(self):
        """Test _get_parser_class returns refinement when registered."""
        factory = ParserFactory()
        factory.register_refinement("hdfc", CustomParser)

        parser_class = factory._get_parser_class("hdfc")
        assert parser_class == CustomParser

    def test_get_parser_class_without_refinement(self):
        """Test _get_parser_class returns GenericParser as fallback."""
        factory = ParserFactory()

        parser_class = factory._get_parser_class("hdfc")
        assert parser_class == GenericParser

        parser_class_none = factory._get_parser_class(None)
        assert parser_class_none == GenericParser


class TestFactorySingleton:
    """Test suite for factory singleton functions."""

    def test_get_parser_factory_singleton(self):
        """Test get_parser_factory returns same instance."""
        factory1 = get_parser_factory()
        factory2 = get_parser_factory()

        assert factory1 is factory2

    @patch.object(ParserFactory, "parse")
    def test_parse_statement_convenience(self, mock_parse):
        """Test parse_statement convenience function."""
        mock_statement = ParsedStatement(
            card_last_four="1234",
            statement_month="2025-01-01",
            closing_balance_cents=100000,
        )
        mock_parse.return_value = mock_statement

        pdf_bytes = b"fake pdf"
        result = parse_statement(pdf_bytes)

        assert result == mock_statement
        mock_parse.assert_called_once_with(pdf_bytes, password=None)
