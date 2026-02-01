"""Generic credit card statement parser.

This module provides the GenericParser class which handles common
parsing logic for credit card statements across all banks.
Bank-specific refinements inherit from this and override only
what's different.
"""

import io
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

    # NOTE: Some PDF extractors replace the Rupee symbol with a plain "C" glyph.
    # Treat that as a currency symbol during extraction.
    AMOUNT_PATTERN = r"[₹$C]?\s*([\d,]+\.?\d{0,2})"

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
        # Many banks (incl. HDFC) format this field as "Card No" / "Credit Card No" with masked digits/spaces.
        match = re.search(
            r"(?i)\b(?:Card\s*No|Credit\s+Card\s*No\.?)\b\s*[:\s]+([0-9Xx*\s]{8,30})",
            full_text,
        )
        if match:
            raw = match.group(1)
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 4:
                return digits[-4:]

        # Some extractors output table labels first and values later (column-wise),
        # so the card number can appear without its label. Look for a masked-card token.
        masked = re.search(r"\b\d{4,6}[Xx*]{4,14}\d{2,4}\b", full_text)
        if masked:
            digits = re.sub(r"\D", "", masked.group(0))
            if len(digits) >= 4:
                return digits[-4:]

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
        # (Some banks use a hyphen instead of "to", and may include a comma after the month.)
        date_token = r"(?:\d{1,2}[-/\.]\w{1,9}[-/\.]\d{2,4}|\d{1,2}\s+\w{3,9},?\s+\d{2,4})"
        patterns = [
            rf"Statement\s+(?:Period|Date)[:\s]*({date_token})\s*(?:to|-)\s*({date_token})",
            rf"Billing\s+Period[:\s]*({date_token})\s*(?:to|-)\s*({date_token})",
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Parse the end date and get the month
                end_date_str = match.group(2)
                end_date = self._parse_date(end_date_str)
                # Return first day of the month
                return date(end_date.year, end_date.month, 1)

        # Fallback: find a bare date range anywhere (some PDFs reorder labels/values).
        match = re.search(
            r"(\d{1,2}\s+\w{3,9},?\s+\d{2,4})\s*-\s*(\d{1,2}\s+\w{3,9},?\s+\d{2,4})",
            full_text,
            re.IGNORECASE,
        )
        if match:
            end_date = self._parse_date(match.group(2))
            return date(end_date.year, end_date.month, 1)

        # Fallback: derive month from a single statement date when no range is present.
        match = re.search(
            rf"(?i)\bStatement\s+Date\s*:?\s*({date_token})",
            full_text,
        )
        if match:
            d = self._parse_date(match.group(1))
            return date(d.year, d.month, 1)

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
            r"Total\s+Amount\s+Due[:\s]*" + self.AMOUNT_PATTERN,
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
        date_token = r"(?:\d{1,2}[-/\.]\w{1,9}[-/\.]\d{2,4}|\d{1,2}\s+\w{3,9},?\s+\d{2,4})"
        pattern = rf"Statement\s+Date[:\s]*({date_token})"
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return self._parse_date(match.group(1))
        return None

    def _find_due_date(self, elements: list[Any], full_text: str) -> date | None:
        """Extract payment due date."""
        date_token = r"(?:\d{1,2}[-/\.]\w{1,9}[-/\.]\d{2,4}|\d{1,2}\s+\w{3,9},?\s+\d{2,4})"
        pattern = rf"(?:Payment\s+)?Due\s+Date[:\s]*({date_token})"
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
        transactions = self._extract_transactions_from_text(full_text)
        if transactions:
            return transactions

        # Deterministic fallback: some PDFs extract better via pypdf's text extraction.
        pdf_bytes = getattr(self, "_pdf_bytes", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)):
            return []

        password = getattr(self, "_pdf_password", None)
        normalized_password = password.strip() if isinstance(password, str) else None
        if normalized_password == "":
            normalized_password = None

        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
            if getattr(reader, "is_encrypted", False):
                # Try empty password first (some PDFs are encrypted but have empty user password).
                ok = reader.decrypt(normalized_password or "")
                if not ok:
                    return []

            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return []

        if not extracted or extracted.strip() == "" or extracted == full_text:
            return []

        return self._extract_transactions_from_text(extracted)

    def _extract_transactions_from_text(self, text: str) -> list[ParsedTransaction]:
        transactions: list[ParsedTransaction] = []

        # Heuristic 1: broad regex across the whole text.
        # Format: Date <spaces> Description <spaces> Amount
        pattern = (
            r"(\d{1,2}[-/.]\w{1,9}[-/.]\d{2,4})\s+(.+?)\s+"
            + r"([₹$C]?\s*[-(]?\s*[\d,]+(?:\.\d{1,2})?\s*\)?)"
            + r"(?:\s*([cC][rR]|[dD][rR]))?"
        )

        for match in re.finditer(pattern, text):
            try:
                transaction_date = self._parse_date(match.group(1))
                description = re.sub(r"\s+", " ", match.group(2)).strip()
                raw_amount = match.group(3) or ""
                crdr = (match.group(4) or "").strip().upper()

                is_negative = "-" in raw_amount or ("(" in raw_amount and ")" in raw_amount)
                amount_decimal = self._parse_amount(raw_amount)
                amount_cents = abs(int(amount_decimal * 100))
                if amount_cents == 0:
                    continue

                transaction_type = "debit"
                if crdr == "CR":
                    transaction_type = "credit"
                elif crdr == "DR":
                    transaction_type = "debit"
                elif is_negative:
                    transaction_type = "credit"
                else:
                    lowered = description.lower()
                    if "credit" in lowered or "refund" in lowered:
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
                continue

        # De-dup exact matches (common when both strategies hit the same rows).
        if not transactions:
            return []
        seen: set[tuple[date, str, int, str]] = set()
        uniq: list[ParsedTransaction] = []
        for txn in transactions:
            key = (txn.transaction_date, txn.description, txn.amount_cents, txn.transaction_type)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(txn)
        return uniq

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
            "%d.%m.%Y",  # 15.01.2025
            "%d/%m/%y",  # 15/01/25
            "%d-%m-%y",  # 15-01-25
            "%d.%m.%y",  # 15.01.25
            "%d %b, %Y",  # 13 Sep, 2025
            "%d %B, %Y",  # 13 September, 2025
            "%d %b %Y",  # 13 Sep 2025
            "%d %B %Y",  # 13 September 2025
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
        raw = text.strip()
        # Remove common debit/credit suffixes/prefixes.
        raw = re.sub(r"(?i)\b(cr|dr)\b", "", raw).strip()
        # Some statements show negative amounts as "(1,234.56)" or "123.45-".
        raw = raw.replace("(", "").replace(")", "").strip()
        if raw.endswith("-"):
            raw = raw[:-1].strip()
        if raw.startswith("-"):
            raw = raw[1:].strip()
        # Remove currency symbols and whitespace
        text = re.sub(r"[₹$C\s]", "", raw)
        # Remove thousands separators
        text = text.replace(",", "")

        try:
            return Decimal(text)
        except Exception as e:
            raise ValueError(f"Could not parse amount: {text}") from e
