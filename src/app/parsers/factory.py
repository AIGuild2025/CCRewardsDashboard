"""Parser factory for routing statements to appropriate parsers.

This module orchestrates the parsing workflow:
1. Extract PDF elements using PDFExtractor
2. Detect bank using BankDetector
3. Select appropriate parser (GenericParser or bank-specific refinement)
4. Parse and return structured data
"""

import logging
from typing import Any

from app.parsers.detector import BankDetector
from app.parsers.extractor import PDFExtractor
from app.parsers.generic import GenericParser
from app.parsers.refinements import AmexParser, HDFCParser, SBIParser
from app.schemas.internal import ParsedStatement

logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for parsing credit card statements.

    The factory handles the complete parsing workflow:
    - Extracts text/tables from PDF bytes
    - Detects which bank issued the statement
    - Routes to appropriate parser (with graceful fallback)
    - Returns structured ParsedStatement

    Bank-specific refinements can be registered to override GenericParser
    for specific banks when needed.

    Example:
        >>> factory = ParserFactory()
        >>> statement = factory.parse(pdf_bytes)
        >>> print(f"Bank: {statement.bank_code}")
        >>> print(f"Card: {statement.card_last_four}")
    """

    def __init__(
        self,
        extractor: PDFExtractor | None = None,
        detector: BankDetector | None = None,
    ):
        """Initialize the parser factory.

        Args:
            extractor: PDF extractor instance (default: new PDFExtractor)
            detector: Bank detector instance (default: new BankDetector)
        """
        self.extractor = extractor or PDFExtractor()
        self.detector = detector or BankDetector()

        # Registry of bank-specific parser refinements
        # Format: {"bank_code": ParserClass}
        self._refinements: dict[str, type[GenericParser]] = {}

    def parse(self, pdf_bytes: bytes, password: str | None = None) -> ParsedStatement:
        """Parse a credit card statement from PDF bytes.

        Complete workflow:
        1. Extract elements from PDF
        2. Detect bank from text patterns
        3. Select appropriate parser (refinement or generic)
        4. Parse and return structured data

        Args:
            pdf_bytes: PDF file content as bytes
            password: Optional password for encrypted PDFs

        Returns:
            ParsedStatement with extracted data

        Raises:
            PDFExtractionError: If PDF extraction fails
            ValueError: If required fields cannot be parsed
        """
        # Step 1: Extract PDF elements
        elements = self.extractor.extract(pdf_bytes, password=password)
        print(f"[PARSER] Extracted {len(elements)} elements from PDF")

        # Step 2: Detect bank
        bank_code = self.detector.detect_from_elements(elements)
        print(f"[PARSER] Detected bank: {bank_code or 'unknown (using GenericParser)'}")
        print(f"[PARSER] Registered banks: {list(self._refinements.keys())}")

        # Step 3: Select parser
        parser_class = self._get_parser_class(bank_code)
        parser = parser_class()
        parser.bank_code = bank_code  # Set for inclusion in result
        print(f"[PARSER] Using parser: {parser_class.__name__}")

        # Step 4: Parse
        statement = parser.parse(elements)
        print(f"[PARSER] Parsed statement: card={statement.card_last_four}, "
              f"transactions={len(statement.transactions)}, "
              f"month={statement.statement_month}")

        return statement

    def register_refinement(self, bank_code: str, parser_class: type[GenericParser]):
        """Register a bank-specific parser refinement.

        This allows adding specialized parsers for specific banks
        that need custom logic beyond what GenericParser provides.

        Example:
            >>> from app.parsers.refinements.hdfc import HDFCParser
            >>> factory.register_refinement("hdfc", HDFCParser)

        Args:
            bank_code: Bank code (e.g., "hdfc", "amex")
            parser_class: Parser class (must inherit from GenericParser)
        """
        if not issubclass(parser_class, GenericParser):
            raise ValueError(
                f"Parser class must inherit from GenericParser, got {parser_class}"
            )

        self._refinements[bank_code] = parser_class

    def unregister_refinement(self, bank_code: str):
        """Remove a bank-specific parser refinement.

        After removal, the bank will use GenericParser.

        Args:
            bank_code: Bank code to remove
        """
        self._refinements.pop(bank_code, None)

    def get_registered_banks(self) -> list[str]:
        """Get list of banks with registered refinements.

        Returns:
            List of bank codes with custom parsers
        """
        return list(self._refinements.keys())

    def _get_parser_class(self, bank_code: str | None) -> type[GenericParser]:
        """Get parser class for a bank code.

        Args:
            bank_code: Detected bank code or None

        Returns:
            Parser class (refinement if registered, else GenericParser)
        """
        if bank_code and bank_code in self._refinements:
            return self._refinements[bank_code]

        # Graceful fallback to GenericParser
        return GenericParser


# Singleton factory instance for global use
_factory_instance: ParserFactory | None = None


def get_parser_factory() -> ParserFactory:
    """Get or create the global ParserFactory instance.

    Returns:
        Global ParserFactory singleton
    """
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = ParserFactory()
        # Register bank-specific refinements
        _factory_instance.register_refinement("hdfc", HDFCParser)
        _factory_instance.register_refinement("amex", AmexParser)
        _factory_instance.register_refinement("sbi", SBIParser)
    return _factory_instance


def parse_statement(pdf_bytes: bytes, password: str | None = None) -> ParsedStatement:
    """Convenience function to parse a statement using the global factory.

    Args:
        pdf_bytes: PDF file content as bytes
        password: Optional password for encrypted PDFs

    Returns:
        ParsedStatement with extracted data
    """
    factory = get_parser_factory()
    return factory.parse(pdf_bytes, password=password)
