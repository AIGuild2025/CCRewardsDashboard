"""American Express parser refinement.

Supports:
- AmEx US statements (often MM/DD/YYYY).
- AmEx India statements (month-name day for transactions + DD/MM/YYYY in headers).

This refinement focuses on making transaction extraction robust for the AmEx formats
we see in practice while keeping the rest of the parsing logic generic.
"""

import re
from datetime import date, datetime
from typing import Any

from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedTransaction


class AmexParser(GenericParser):
    """Parser refinement for American Express credit card statements.

    Amex-specific behaviors:
    - Date formats:
      - MM/DD/YYYY (common in US)
      - DD/MM/YYYY (common in India)
      - Month-name formats like "October 9, 2025"
    - Card number:
      - 5-digit account ending (e.g., "Account Ending 12345")
      - masked formats like "XXXX-XXXXXX-73008"
    - Transactions (India statements commonly omit year per row)
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

        # Common India numeric formats (DD/MM/YYYY)
        india_formats = [
            "%d/%m/%Y",  # 23/10/2025
            "%d/%m/%y",  # 23/10/25
            "%d-%m-%Y",  # 23-10-2025
            "%d-%m-%y",  # 23-10-25
        ]
        for fmt in india_formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

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

        # Month-name formats (used in some AmEx PDFs)
        month_formats = [
            "%B %d %Y",   # October 23 2025
            "%B %d, %Y",  # October 23, 2025
            "%b %d %Y",   # Oct 23 2025
            "%b %d, %Y",  # Oct 23, 2025
        ]
        for fmt in month_formats:
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
            r"[xX]{4}-[xX]{6}-(\d{5})",  # XXXX-XXXXXX-73008
            r"card\s+number\s+[xX]{4}-[xX]{6}-(\d{5})",  # Card Number XXXX-XXXXXX-73008
        ]

        for pattern in amex_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Return last 4 of the 5 digits for consistency
                five_digits = match.group(1)
                return five_digits[-4:]

        # Fallback to GenericParser (handles standard 4-digit patterns)
        return super()._find_card_number(elements, full_text)

    def _find_statement_period(self, elements: list[Any], full_text: str) -> date:
        """Extract statement period for common AmEx layouts.

        AmEx India statements commonly show:
          "Statement Period From  September 24  to October 23, 2025"

        The per-transaction rows may omit year, so we use the end date's year as
        the statement year and derive the statement month from the end date.
        """
        patterns = [
            # Unstructured can collapse spaces, e.g. "Statement PeriodFrom September 24 toOctober 23, 2025"
            r"Statement\s*Period\s*From\s*([A-Za-z]{3,9})\s*(\d{1,2})\s*to\s*([A-Za-z]{3,9})\s*(\d{1,2})\s*,?\s*(\d{4})",
        ]

        for pattern in patterns:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if not m:
                continue

            end_month, end_day, end_year = m.group(3), m.group(4), m.group(5)
            end_date = self._parse_date(f"{end_month} {end_day} {end_year}")
            return date(end_date.year, end_date.month, 1)

        return super()._find_statement_period(elements, full_text)

    def _find_closing_balance(self, elements: list[Any], full_text: str) -> int:
        """Extract closing balance for AmEx India summary layout.

        Example layout:
          "Opening Balance Rs New Credits Rs New Debits Rs Closing Balance Rs Minimum Payment Rs"
          "6,031.83 - 7,260.40 + 14,022.15 = 12,793.58 640.00"
        """
        # Unstructured can collapse the summary into a single line, e.g.:
        # "Opening Balance Rs...=12,793.58 640.00"
        m = re.search(
            r"Opening\s+Balance.*?=\s*([\d,]+\.\d{2})",
            full_text,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            amount_decimal = self._parse_amount(m.group(1))
            return int(amount_decimal * 100)

        return super()._find_closing_balance(elements, full_text)

    def _extract_transactions(
        self, elements: list[Any], full_text: str
    ) -> list[ParsedTransaction]:
        """Extract transactions from common AmEx India statement text.

        Transactions often appear as one row per line:
          "October 9 Billdesk*AMAZON MUM 1,560.16"
        Some PDFs break the credit marker onto the next line:
          "October 9 Billdesk*AMAZON MUM 0.30"
          "CR"
        """

        def _infer_statement_year(text: str) -> int | None:
            # Prefer year from statement period end date.
            m = re.search(
                r"Statement\s*Period\s*From.*?to\s*[A-Za-z]{3,9}\s*\d{1,2}\s*,?\s*(\d{4})",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if m:
                return int(m.group(1))

            # Fallback: any explicit dd/mm/yyyy date near the top of the statement.
            m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
            if m:
                return int(m.group(3))

            return None

        month_re = (
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        )
        row_re = re.compile(
            rf"^{month_re}\s+(\d{{1,2}})\s+(.+?)\s+([\d,]+\.\d{{2}})(?:\s*(CR|DR))?$",
            re.IGNORECASE,
        )

        def _parse_text(text: str) -> list[ParsedTransaction]:
            year = _infer_statement_year(text)
            txns: list[ParsedTransaction] = []
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            i = 0
            while i < len(lines):
                line = lines[i]
                m = row_re.match(line)
                if not m:
                    i += 1
                    continue

                month_name = m.group(1)
                day = int(m.group(2))
                desc = m.group(3).strip()
                amt = m.group(4).replace(",", "")
                marker = m.group(5)

                # Some PDFs put CR/DR on the next line
                if not marker and i + 1 < len(lines) and lines[i + 1].strip().upper() in {"CR", "DR"}:
                    marker = lines[i + 1].strip().upper()
                    i += 1  # consume the marker line

                # Ignore non-transaction noise rows
                if desc.lower().startswith("card number"):
                    i += 1
                    continue
                if desc.lower().startswith("new domestic transactions"):
                    i += 1
                    continue

                # Infer year: use statement year when available; otherwise fall back to current year.
                y = year or datetime.utcnow().year
                try:
                    txn_date = self._parse_date(f"{month_name} {day} {y}")
                except Exception:
                    i += 1
                    continue

                amount_cents = int(float(amt) * 100)
                transaction_type = "debit"
                if (marker or "").upper() == "CR" or "payment received" in desc.lower():
                    transaction_type = "credit"

                txns.append(
                    ParsedTransaction(
                        transaction_date=txn_date,
                        description=desc,
                        amount_cents=amount_cents,
                        transaction_type=transaction_type,
                        category=None,
                    )
                )
                i += 1

            return txns

        transactions = _parse_text(full_text)

        # Deterministic fallback: also try plain text extraction from the raw PDF bytes.
        pdf_text_override = getattr(self, "_pdf_text_override", None)
        fb_text: str | None = None
        if isinstance(pdf_text_override, str) and pdf_text_override.strip():
            fb_text = pdf_text_override
        else:
            pdf_bytes = getattr(self, "_pdf_bytes", None)
            if isinstance(pdf_bytes, (bytes, bytearray)) and pdf_bytes:
                try:
                    import io
                    from pypdf import PdfReader

                    reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
                    if getattr(reader, "is_encrypted", False):
                        reader.decrypt(getattr(self, "_pdf_password", None) or "")
                    fb_text = "\n".join((p.extract_text() or "") for p in reader.pages)
                except Exception:
                    fb_text = None

        if fb_text:
            fb_txns = _parse_text(fb_text)
            if len(fb_txns) > len(transactions):
                transactions = fb_txns

        return transactions if transactions else super()._extract_transactions(elements, full_text)
