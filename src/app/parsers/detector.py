"""Bank detection from PDF text content.

This module identifies which bank issued a credit card statement
based on text patterns found in the PDF.
"""

import re
from typing import Any


class BankDetector:
    """Detects the issuing bank from credit card statement text.

    The detector searches for bank-specific patterns (names, URLs, logos)
    in the extracted PDF text to identify which bank issued the statement.

    Supported banks:
        - hdfc: HDFC Bank (India)
        - icici: ICICI Bank (India)
        - sbi: State Bank of India / SBI Card
        - amex: American Express
        - citi: Citibank
        - chase: JPMorgan Chase

    Example:
        >>> detector = BankDetector()
        >>> bank_code = detector.detect(full_text)
        >>> if bank_code:
        ...     print(f"Detected: {bank_code}")
        ... else:
        ...     print("Unknown bank - will use GenericParser")
    """

    # Bank detection patterns (case-insensitive)
    BANK_PATTERNS = {
        "hdfc": [
            r"HDFC\s+Bank",
            r"hdfcbank\.com",
            r"HDFC\s+Credit\s+Card",
        ],
        "icici": [
            r"ICICI\s+Bank",
            r"icicibank\.com",
            r"ICICI\s+Credit\s+Card",
        ],
        "sbi": [
            r"State\s+Bank\s+of\s+India",
            r"SBI\s+Card",
            r"sbicard\.com",
        ],
        "amex": [
            r"American\s+Express",
            r"americanexpress\.com",
            r"AMEX",
        ],
        "citi": [
            r"Citibank",
            r"citi\.com",
            r"Citi\s+Credit\s+Card",
        ],
        "chase": [
            r"JPMorgan\s+Chase",
            r"chase\.com",
            r"Chase\s+Credit\s+Card",
        ],
    }

    def __init__(self):
        """Initialize the bank detector with compiled regex patterns."""
        # Compile patterns for better performance
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for bank_code, patterns in self.BANK_PATTERNS.items():
            self._compiled_patterns[bank_code] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def detect(self, text: str) -> str | None:
        """Detect the bank from statement text.

        Args:
            text: Full text content extracted from the PDF

        Returns:
            Bank code (e.g., "hdfc", "amex") or None if no match found
        """
        if not text:
            return None

        # Check each bank's patterns
        for bank_code, patterns in self._compiled_patterns.items():
            if self._matches_bank(text, patterns):
                return bank_code

        return None

    def detect_from_elements(self, elements: list[Any]) -> str | None:
        """Detect bank from Unstructured elements directly.

        Args:
            elements: List of Element objects from PDFExtractor

        Returns:
            Bank code or None if no match found
        """
        # Concatenate all element text
        full_text = "\n".join(str(element) for element in elements)
        return self.detect(full_text)

    def _matches_bank(self, text: str, patterns: list[re.Pattern]) -> bool:
        """Check if any pattern matches the text.

        Args:
            text: Text to search
            patterns: List of compiled regex patterns

        Returns:
            True if any pattern matches
        """
        return any(pattern.search(text) for pattern in patterns)

    def get_supported_banks(self) -> list[str]:
        """Get list of supported bank codes.

        Returns:
            List of bank codes (e.g., ["hdfc", "icici", ...])
        """
        return list(self.BANK_PATTERNS.keys())

    def add_pattern(self, bank_code: str, pattern: str) -> None:
        """Add a new detection pattern for a bank.

        This allows extending detection rules at runtime.

        Args:
            bank_code: Bank code (e.g., "hdfc")
            pattern: Regex pattern to match
        """
        if bank_code not in self._compiled_patterns:
            self._compiled_patterns[bank_code] = []

        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        self._compiled_patterns[bank_code].append(compiled_pattern)
