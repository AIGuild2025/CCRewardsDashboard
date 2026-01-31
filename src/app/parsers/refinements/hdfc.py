"""HDFC Bank parser refinement.

Overrides date parsing to handle HDFC's DD-MMM-YY format.
"""

from datetime import date, datetime

from app.parsers.generic import GenericParser


class HDFCParser(GenericParser):
    """Parser refinement for HDFC Bank credit card statements.

    HDFC-specific behaviors:
    - Date format: DD-MMM-YY (e.g., "15-Jan-25")
    - Everything else uses GenericParser defaults
    """

    def __init__(self):
        """Initialize HDFC parser."""
        super().__init__()
        self.bank_code = "hdfc"

    def _parse_date(self, text: str) -> date:
        """Parse HDFC date format (DD-MMM-YY).

        HDFC uses formats like:
        - 15-Jan-25
        - 15-Jan-2025
        - 15/01/2025

        Args:
            text: Date string from statement

        Returns:
            Parsed date object

        Raises:
            ValueError: If date cannot be parsed
        """
        text = text.strip()

        # Try HDFC-specific formats first
        formats = [
            "%d-%b-%y",  # 15-Jan-25
            "%d-%b-%Y",  # 15-Jan-2025
            "%d/%m/%Y",  # 15/01/2025
            "%d/%m/%y",  # 15/01/25
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        # Fallback to GenericParser formats
        return super()._parse_date(text)
