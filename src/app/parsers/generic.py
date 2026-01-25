"""Generic credit card statement parser.

This module provides the GenericParser class which handles common
parsing logic for credit card statements across all banks.
Bank-specific refinements inherit from this and override only
what's different.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.schemas.internal import ParsedStatement, ParsedTransaction


class GenericParser:
    """Universal parser for credit card statements.

    This parser extracts common fields from any credit card statement
    using pattern matching and heuristics. It works for ~90% of banks
    without modification.

    Subclasses can override specific methods to handle bank-specific quirks:
        - _parse_date(): Different date formats
        - _parse_amount(): Different currency formats
        - _find_card_number(): Different card number patterns
        - _find_rewards(): Different reward point locations

    Example:
        >>> parser = GenericParser()
        >>> statement = parser.parse(elements)
        >>> print(f"Card: {statement.card_last_four}")
    """

    # Common patterns for field extraction
    CARD_PATTERNS = [
        r"Card\s+(?:Number|ending|ending\s+in)[:\s]*[xX*]{4,}\s*(\d{4})",
        r"Card\s+[xX*]{4,}\s*(\d{4})",
        r"[xX*]{12}(\d{4})",  # xxxx xxxx xxxx 1234
    ]

    AMOUNT_PATTERN = r"[₹$]?\s*([\d,]+\.?\d{0,2})"

    def __init__(self):
        """Initialize the generic parser."""
        self.bank_code: str | None = None

    def parse(self, elements: list[Any]) -> ParsedStatement:
        """Parse a credit card statement from extracted PDF elements.

        Args:
            elements: List of Element objects from PDFExtractor

        Returns:
            ParsedStatement with extracted data

        Raises:
            ValueError: If required fields cannot be extracted
        """
        full_text = "\n".join(str(element) for element in elements)

        # Extract required fields
        card_last_four = self._find_card_number(elements, full_text)
        statement_month = self._find_statement_period(elements, full_text)
        closing_balance_cents = self._find_closing_balance(elements, full_text)
        reward_points = self._find_rewards(elements, full_text)
        
        # For banks that show earned vs balance separately, override this
        reward_points_earned = reward_points  # Default: assume balance = earned

        # Extract transactions
        transactions = self._extract_transactions(elements, full_text)

        # Extract optional fields
        statement_date = self._find_statement_date(elements, full_text)
        due_date = self._find_due_date(elements, full_text)
        minimum_due_cents = self._find_minimum_due(elements, full_text)

        return ParsedStatement(
            card_last_four=card_last_four,
            statement_month=statement_month,
            closing_balance_cents=closing_balance_cents,
            reward_points=reward_points,
            reward_points_earned=reward_points_earned,
            transactions=transactions,
            bank_code=self.bank_code,
            statement_date=statement_date,
            due_date=due_date,
            minimum_due_cents=minimum_due_cents,
        )

    def _find_card_number(self, elements: list[Any], full_text: str) -> str:
        """Extract last 4 digits of card number.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            Last 4 digits as string

        Raises:
            ValueError: If card number not found
        """
        for pattern in self.CARD_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(1)

        raise ValueError("Could not find card number in statement")

    def _find_statement_period(self, elements: list[Any], full_text: str) -> date:
        """Extract statement period (first day of month).

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            First day of the statement month

        Raises:
            ValueError: If statement period not found
        """
        # Common patterns for statement period
        patterns = [
            r"Statement\s+(?:Period|Date)[:\s]*(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})",
            r"Billing\s+Period[:\s]*(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Parse the end date and get the month
                end_date_str = match.group(2)
                end_date = self._parse_date(end_date_str)
                # Return first day of the month
                return date(end_date.year, end_date.month, 1)

        raise ValueError("Could not find statement period")

    def _find_closing_balance(self, elements: list[Any], full_text: str) -> int:
        """Extract closing balance in cents.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            Balance in cents

        Raises:
            ValueError: If balance not found
        """
        patterns = [
            r"Closing\s+Balance[:\s]*" + self.AMOUNT_PATTERN,
            r"Total\s+Balance[:\s]*" + self.AMOUNT_PATTERN,
            r"Amount\s+Due[:\s]*" + self.AMOUNT_PATTERN,
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                amount_decimal = self._parse_amount(amount_str)
                return int(amount_decimal * 100)

        raise ValueError("Could not find closing balance")

    def _find_rewards(self, elements: list[Any], full_text: str) -> int:
        """Extract reward points.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            Reward points (0 if not found)
        """
        patterns = [
            r"Reward\s+Points[:\s]*(\d+)",
            r"Points\s+Earned[:\s]*(\d+)",
            r"Total\s+Points[:\s]*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 0  # Not all statements have rewards

    def _find_statement_date(self, elements: list[Any], full_text: str) -> date | None:
        """Extract statement generation date."""
        pattern = r"Statement\s+Date[:\s]*(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})"
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return self._parse_date(match.group(1))
        return None

    def _find_due_date(self, elements: list[Any], full_text: str) -> date | None:
        """Extract payment due date."""
        pattern = r"(?:Payment\s+)?Due\s+Date[:\s]*(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})"
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return self._parse_date(match.group(1))
        return None

    def _find_minimum_due(self, elements: list[Any], full_text: str) -> int | None:
        """Extract minimum payment due in cents."""
        pattern = r"Minimum\s+(?:Payment\s+)?Due[:\s]*" + self.AMOUNT_PATTERN
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            amount_decimal = self._parse_amount(match.group(1))
            return int(amount_decimal * 100)
        return None

    def _extract_transactions(
        self, elements: list[Any], full_text: str
    ) -> list[ParsedTransaction]:
        """Extract all transactions from the statement.

        This is a simplified implementation. Real-world parsing would
        need more sophisticated table extraction.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            List of ParsedTransaction objects
        """
        transactions = []

        # Look for transaction table pattern
        # Format: Date | Description | Amount
        pattern = r"(\d{1,2}[-/]\w{3,9}[-/]\d{2,4})\s+(.+?)\s+" + self.AMOUNT_PATTERN

        for match in re.finditer(pattern, full_text):
            try:
                transaction_date = self._parse_date(match.group(1))
                description = match.group(2).strip()
                amount_str = match.group(3)
                amount_decimal = self._parse_amount(amount_str)
                amount_cents = int(amount_decimal * 100)

                # Determine transaction type (debit vs credit)
                transaction_type = "debit"
                if "credit" in description.lower() or "refund" in description.lower():
                    transaction_type = "credit"

                transactions.append(
                    ParsedTransaction(
                        transaction_date=transaction_date,
                        description=description,
                        amount_cents=amount_cents,
                        transaction_type=transaction_type,
                    )
                )
            except Exception:
                # Skip malformed transactions
                continue

        return transactions

    def _parse_date(self, text: str) -> date:
        """Parse date from text.

        Override this method in subclasses for bank-specific date formats.

        Supported formats:
            - DD-MMM-YY (15-Jan-25)
            - DD/MM/YYYY (15/01/2025)
            - DD-MM-YYYY (15-01-2025)

        Args:
            text: Date string

        Returns:
            Parsed date

        Raises:
            ValueError: If date cannot be parsed
        """
        text = text.strip()

        # Try common formats
        formats = [
            "%d-%b-%y",  # 15-Jan-25
            "%d-%b-%Y",  # 15-Jan-2025
            "%d/%m/%Y",  # 15/01/2025
            "%d-%m-%Y",  # 15-01-2025
            "%d/%m/%y",  # 15/01/25
            "%d-%m-%y",  # 15-01-25
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {text}")

    def _parse_amount(self, text: str) -> Decimal:
        """Parse amount from text.

        Override this method in subclasses for bank-specific currency formats.

        Handles:
            - ₹1,23,456.00 (Indian format)
            - $1,234.56 (US format)
            - 1234.56 (plain decimal)

        Args:
            text: Amount string

        Returns:
            Amount as Decimal

        Raises:
            ValueError: If amount cannot be parsed
        """
        # Remove currency symbols and whitespace
        text = re.sub(r"[₹$\s]", "", text)
        # Remove thousands separators
        text = text.replace(",", "")

        try:
            return Decimal(text)
        except Exception as e:
            raise ValueError(f"Could not parse amount: {text}") from e
