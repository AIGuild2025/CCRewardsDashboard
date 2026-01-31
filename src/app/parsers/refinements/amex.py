"""American Express parser refinement.

Overrides date parsing for US format and card number extraction for 5-digit account numbers.
"""

import re
from datetime import date, datetime
from typing import Any

from app.parsers.generic import GenericParser


class AmexParser(GenericParser):
    """Parser refinement for American Express credit card statements.

    Amex-specific behaviors:
    - Date format: MM/DD/YYYY (US format)
    - Card number: Shows 5-digit account ending (xxxxx xxxxx x12345)
    - Everything else uses GenericParser defaults
    """

    def __init__(self):
        """Initialize Amex parser."""
        super().__init__()
        self.bank_code = "amex"

    def _parse_date(self, text: str) -> date:
        """Parse American Express date format (MM/DD/YYYY).

        Amex uses US date formats:
        - 01/15/2025 (MM/DD/YYYY)
        - 1/15/2025
        - 01-15-2025

        Args:
            text: Date string from statement

        Returns:
            Parsed date object

        Raises:
            ValueError: If date cannot be parsed
        """
        text = text.strip()

        # Try US formats first (MM/DD/YYYY)
        us_formats = [
            "%m/%d/%Y",  # 01/15/2025
            "%m/%d/%y",  # 01/15/25
            "%m-%d-%Y",  # 01-15-2025
            "%m-%d-%y",  # 01-15-25
        ]

        for fmt in us_formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        # Fallback to GenericParser formats (for edge cases)
        return super()._parse_date(text)

    def _find_card_number(self, elements: list[Any], full_text: str) -> str:
        """Extract card number from Amex statement.

        Amex shows 5-digit account endings instead of 4:
        - "Account Ending 12345"
        - "Card ending in 12345"

        Returns last 4 digits to maintain consistency with other parsers.

        Args:
            elements: List of PDF elements
            full_text: Concatenated text from all elements

        Returns:
            Last 4 digits of card number

        Raises:
            ValueError: If card number cannot be found
        """
        # Try Amex-specific patterns first (5-digit account ending)
        amex_patterns = [
            r"account\s+ending\s+in[\s:]*(\d{5})",
            r"account\s+ending[\s:]*(\d{5})",
            r"card\s+ending\s+in[\s:]*(\d{5})",
            r"xxxxx\s+xxxxx\s+x(\d{5})",
        ]

        for pattern in amex_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Return last 4 of the 5 digits for consistency
                five_digits = match.group(1)
                return five_digits[-4:]

        # Fallback to GenericParser (handles standard 4-digit patterns)
        return super()._find_card_number(elements, full_text)
