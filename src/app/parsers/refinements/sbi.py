"""SBI Bank parser refinement.

Overrides card number detection and date parsing to handle SBI's formats.
"""

import logging
import io
import re
from datetime import date, datetime
from itertools import permutations
from typing import Any

from pypdf import PdfReader

from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedTransaction


logger = logging.getLogger(__name__)


class SBIParser(GenericParser):
    """Parser refinement for SBI (State Bank of India) credit card statements.

    SBI-specific behaviors:
    - Card number format: Different patterns than standard
    - Date format: DD/MM/YYYY or DD-MM-YYYY
    - Everything else uses GenericParser defaults
    """

    # SBI-specific card number patterns
    SBI_CARD_PATTERNS = [
        r"[xX]{4}\s+[xX]{4}\s+[xX]{4}\s+[xX]{2}(\d{2})",  # XXXX XXXX XXXX XX95 (SBI format)
        r"[xX*]{4}[\s-]+[xX*]{4}[\s-]+[xX*]{4}[\s-]+[xX*]{2}(\d{2})",  # XXXX-XXXX-XXXX-XX95
        r"Card\s+No[.:\s]*[xX*]{4,}[\s-]*[xX*]{4,}[\s-]*[xX*]{4,}[\s-]*[xX*]{0,2}(\d{2,4})",  # Card No. xxxx xxxx xxxx xx95
        r"Card\s+Number[:\s]*[xX*]{4,}[\s-]*[xX*]{4,}[\s-]*[xX*]{4,}[\s-]*[xX*]{0,2}(\d{2,4})",  # Card Number
        r"(?:ending|ending\s+in|ends\s+with)[:\s]*[xX*]{0,2}(\d{2,4})",  # ending in XX95 or 95
        r"[xX*]{4,}[\s-]+[xX*]{4,}[\s-]+[xX*]{4,}[\s-]+(\d{4})",  # xxxx xxxx xxxx 1234
    ]

    def parse(self, elements: list[Any]):
        """Override parse to capture reward_points_earned separately.
        
        SBI shows both earned this period and total balance.
        """
        # Initialize the earned points tracker
        self._reward_points_earned = 0
        
        # Call parent parse which will call our _find_rewards()
        parsed = super().parse(elements)
        
        # Update with the earned value we captured
        parsed.reward_points_earned = self._reward_points_earned
        
        return parsed

    def __init__(self):
        """Initialize SBI parser."""
        super().__init__()
        self.bank_code = "sbi"

    def _find_card_number(self, elements: list[Any], full_text: str) -> str:
        """Extract last 4 digits of card number from SBI statement.

        SBI statements show card numbers like: XXXX XXXX XXXX XX95
        where only the last 2 digits are visible. We extract those 2 digits
        and pad with 'XX' prefix to maintain the 4-character format.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            Last 4 characters as string (e.g., "XX95" or "1234")

        Raises:
            ValueError: If card number not found
        """
        logger.debug("Attempting to find card number (SBI)")
        # Try SBI-specific patterns first
        for i, pattern in enumerate(self.SBI_CARD_PATTERNS):
            match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                digits = match.group(1)
                # If only 2 digits found, pad with XX prefix
                if len(digits) == 2:
                    result = f"XX{digits}"
                    logger.debug("Found card number (SBI pattern)", extra={"pattern": i + 1})
                    return result
                logger.debug("Found card number (SBI pattern)", extra={"pattern": i + 1})
                return digits

        # Fall back to generic patterns
        logger.debug("SBI card patterns failed; trying generic patterns")
        try:
            result = super()._find_card_number(elements, full_text)
            logger.debug("Found card number via generic patterns")
            return result
        except ValueError:
            # If still not found, provide helpful error
            raise ValueError(
                "Could not find card number in SBI statement. "
                "Looked for patterns like 'XXXX XXXX XXXX XX95', "
                "'Card No xxxx xxxx xxxx xx95', or 'ending in 95'."
            )

    def _parse_date(self, text: str) -> date:
        """Parse SBI date format.

        SBI commonly uses:
        - DD/MM/YYYY (e.g., "15/01/2025")
        - DD-MM-YYYY (e.g., "15-01-2025")
        - DD MMM YY (e.g., "15 Dec 25") - 2-digit year
        - DD MMM YYYY (e.g., "15 Jan 2026") - 4-digit year

        Args:
            text: Date string from statement

        Returns:
            Parsed date object

        Raises:
            ValueError: If date cannot be parsed
        """
        text = text.strip()

        # Try SBI-specific formats first
        formats = [
            "%d %b %y",  # 15 Dec 25 (2-digit year) - TRANSACTIONS FORMAT
            "%d %b %Y",  # 15 Jan 2025 (4-digit year)
            "%d %B %Y",  # 15 January 2025
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

        # Fall back to generic date parsing
        return super()._parse_date(text)

    def _find_rewards(self, elements: list[Any], full_text: str) -> int:
        """Extract SBI reward points closing balance.
        
        SBI format: Numbers appear BEFORE the header
        Example text:
            3988 57 0 4045
            Previous Balance Earned
            Redeemed/Expired
            /Forfeited Closing Balance Points Expiry Details
        
        This method returns the closing balance. Override parse() to also capture earned.
        
        Returns:
            Closing balance of reward points
        """
        logger.debug("Extracting reward points (SBI)")

        # SBI reward summary is usually a 4-number row:
        #   Previous Balance, Earned, Redeemed/Expired, Closing Balance
        # But OCR/table extraction can reorder both the headers and the numbers.
        #
        # Robust approach:
        # - Find any 4-number sequences near reward-related keywords
        # - Assign (previous, earned, redeemed, closing) by checking the invariant:
        #       previous + earned - redeemed == closing
        normalized_text = re.sub(r"\s+", " ", full_text)

        def _try_assign(nums: list[int]) -> tuple[int, int, int, int] | None:
            """Try to map 4 numbers onto (previous, earned, redeemed, closing).

            SBI's invariant: previous + earned - redeemed == closing.

            OCR can reorder the columns, and in rare cases the invariant may be
            satisfied by multiple permutations. When that happens, we pick the
            most plausible assignment via a small heuristic score.
            """

            candidates: list[tuple[int, int, int, int]] = []
            for idxs in permutations(range(4), 4):
                previous = nums[idxs[0]]
                earned = nums[idxs[1]]
                redeemed = nums[idxs[2]]
                closing = nums[idxs[3]]
                if previous + earned - redeemed == closing:
                    candidates.append((previous, earned, redeemed, closing))

            if not candidates:
                return None

            # Heuristic ranking to disambiguate:
            # - Closing balance being the smallest is very unlikely
            # - Prefer closing >= previous (common for typical billing cycles)
            # - Prefer smaller redeemed (often 0) and non-zero earned when possible
            min_val = min(nums)
            max_val = max(nums)

            def score(cand: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
                previous, earned, redeemed, closing = cand
                penalty = 0
                if closing == min_val:
                    penalty += 1000
                if closing < previous:
                    penalty += 100
                # Earned points are usually smaller than the carried forward balance.
                if earned > previous:
                    penalty += 200
                if earned == max_val:
                    penalty += 100
                # Prefer assignments where redeemed is minimal (often 0).
                penalty += redeemed
                # Small nudge toward non-zero earned when possible.
                penalty += 10 if earned == 0 else 0
                # Mild preference for closing being the largest number.
                penalty += 0 if closing == max_val else 5
                return (penalty, redeemed, -earned, -closing)

            return min(candidates, key=score)

        four_num_pattern = r"(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)"
        for match in re.finditer(four_num_pattern, normalized_text):
            # Context filter to avoid false positives (credit limits, interest rates, etc.)
            start, end = match.span()
            context = normalized_text[max(0, start - 220) : min(len(normalized_text), end + 220)]
            ctx = context.lower()

            # Reward section usually includes these words near the row (order may vary).
            if "previous balance" not in ctx or "earned" not in ctx:
                continue

            raw_nums = [match.group(i) for i in range(1, 5)]
            nums = [int(n.replace(",", "")) for n in raw_nums]

            # If a column label appears immediately before the number group,
            # use it as an anchor to avoid ambiguous invariant matches.
            pre = normalized_text[max(0, start - 90) : start].lower()
            post = normalized_text[end : min(len(normalized_text), end + 90)].lower()

            anchored: tuple[int, int, int, int] | None = None
            if "closing balance" in pre:
                closing = nums[0]
                rest = nums[1:]
                for p in permutations(rest, 3):
                    previous, earned, redeemed = p
                    if previous + earned - redeemed == closing:
                        anchored = (previous, earned, redeemed, closing)
                        break
            elif "previous balance" in pre:
                previous = nums[0]
                rest = nums[1:]
                for p in permutations(rest, 3):
                    earned, redeemed, closing = p
                    if previous + earned - redeemed == closing:
                        anchored = (previous, earned, redeemed, closing)
                        break
            elif "earned" in pre:
                earned = nums[0]
                rest = nums[1:]
                for p in permutations(rest, 3):
                    previous, redeemed, closing = p
                    if previous + earned - redeemed == closing:
                        anchored = (previous, earned, redeemed, closing)
                        break
            elif "redeemed" in pre:
                redeemed = nums[0]
                rest = nums[1:]
                for p in permutations(rest, 3):
                    previous, earned, closing = p
                    if previous + earned - redeemed == closing:
                        anchored = (previous, earned, redeemed, closing)
                        break
            elif "previous balance" in post and "earned" in post:
                # Common layout: the 4-number row immediately precedes the header,
                # and the order is Previous, Earned, Redeemed, Closing.
                previous, earned, redeemed, closing = nums
                if previous + earned - redeemed == closing:
                    anchored = (previous, earned, redeemed, closing)

            assigned = anchored or _try_assign(nums)
            if not assigned:
                continue

            previous, earned, redeemed, closing = assigned
            logger.debug(
                "Reward points found via invariant",
                extra={
                    "previous": previous,
                    "earned": earned,
                    "redeemed": redeemed,
                    "closing": closing,
                },
            )
            self._reward_points_earned = earned
            return closing

        logger.debug("Reward points not found; defaulting to 0")
        self._reward_points_earned = 0
        return 0

    def _extract_transactions(
        self, elements: list[Any], full_text: str
    ) -> list[ParsedTransaction]:
        """Extract transactions from SBI statement.

        SBI format:
        DD MMM YY MERCHANT_NAME AMOUNT C/D
        Example: 15 Dec 25 APOLLO PHARMACIES LIMI IN 1,138.82 D

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            List of parsed transactions
        """
        logger.debug("Extracting transactions (SBI)")
        transactions: list[ParsedTransaction] = []

        date_token = re.compile(
            r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}",
            re.IGNORECASE,
        )
        row_date_pat = r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}"
        # Row match that can find multiple transactions inside one stitched line.
        # We do not require an immediate next-date lookahead because some extractors
        # can insert header text between rows (e.g., "TRANSACTIONS FOR ...").
        row_pat = re.compile(
            rf"(?P<date>{row_date_pat})\s+(?P<merchant>.+?)\s+"
            rf"(?P<amount>[\d,]+\.\d{{2}})\s*(?P<cd>[CD])\b",
            re.IGNORECASE | re.DOTALL,
        )

        def _clean_merchant_text(text: str) -> str:
            """Clean common OCR/layout artifacts for merchant/description.

            SBI statements can include an extra "value date" column and some PDF
            extractors may interleave the next row's merchant into the current
            row's description. We apply a conservative cleanup:
            - If we see an embedded transaction date token (DD Mon YY), truncate
              at that point (keeps the merchant for this row only).
            - Remove trailing date tokens like "16 Dec 25" which are almost
              always a value-date artifact in the description field.
            """
            original = re.sub(r"\s+", " ", (text or "").strip())
            if not original:
                return original
            s = original

            dates = list(date_token.finditer(s))
            if dates:
                # If there's an embedded date token inside the merchant string,
                # it's almost always the next row bleeding into this row.
                # Keep the part before the first embedded date.
                if dates[0].start() > 0:
                    s = s[: dates[0].start()].rstrip()

            # Strip a trailing value-date, if present.
            s = re.sub(
                r"\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2}\s*$",
                "",
                s,
                flags=re.IGNORECASE,
            )
            cleaned = s.strip()
            # Avoid dropping transactions due to an over-aggressive cleanup.
            return cleaned if cleaned else original

        def _parse_text_to_transactions(text: str) -> list[ParsedTransaction]:
            # Parse line-by-line first (most reliable for SBI; avoids cross-row mixing).
            # Unstructured can wrap long merchants onto the next line, so we stitch
            # continuation lines into the prior row until the next date token.
            txns: list[ParsedTransaction] = []
            stitched_rows: list[str] = []
            current: str | None = None
            for raw_line in text.splitlines():
                line = re.sub(r"\s+", " ", (raw_line or "").strip())
                if not line:
                    continue
                if re.match(rf"^{row_date_pat}\b", line, re.IGNORECASE):
                    if current:
                        stitched_rows.append(current)
                    current = line
                else:
                    if current:
                        current = f"{current} {line}"
            if current:
                stitched_rows.append(current)

            for row in stitched_rows:
                try:
                    for m in row_pat.finditer(row):
                        date_str = m.group("date")
                        merchant = _clean_merchant_text(m.group("merchant"))
                        amount_str = m.group("amount").replace(",", "")
                        txn_type = m.group("cd")

                        txn_date = self._parse_date(date_str)
                        amount_cents = int(float(amount_str) * 100)
                        transaction_type = (
                            "credit" if txn_type.upper() == "C" else "debit"
                        )

                        txns.append(
                            ParsedTransaction(
                                transaction_date=txn_date,
                                description=merchant,
                                amount_cents=amount_cents,
                                transaction_type=transaction_type,
                                category=None,
                            )
                        )
                except Exception as e:
                    logger.debug(
                        "Failed to parse a transaction row",
                        extra={"error_type": type(e).__name__},
                    )
                    continue

            # Last resort: whole-text scan (handles cases where extraction removed newlines).
            if not txns:
                pattern = re.compile(
                    rf"({row_date_pat})\s+(.+?)\s+([\d,]+\.\d{{2}})\s*([CD])\b",
                    re.IGNORECASE | re.DOTALL,
                )
                for match in pattern.finditer(text):
                    try:
                        date_str = match.group(1)
                        merchant = _clean_merchant_text(match.group(2))
                        amount_str = match.group(3).replace(",", "")
                        txn_type = match.group(4)

                        txn_date = self._parse_date(date_str)
                        amount_cents = int(float(amount_str) * 100)
                        transaction_type = (
                            "credit" if txn_type.upper() == "C" else "debit"
                        )

                        txns.append(
                            ParsedTransaction(
                                transaction_date=txn_date,
                                description=merchant,
                                amount_cents=amount_cents,
                                transaction_type=transaction_type,
                                category=None,
                            )
                        )
                    except Exception:
                        continue

            return txns

        def _looks_corrupt(txns: list[ParsedTransaction]) -> bool:
            if not txns:
                return True
            amount_like = re.compile(r"^[\d,]+\.\d{2}\s*[CD]?$", re.IGNORECASE)
            for t in txns:
                desc = (t.description or "").strip()
                if not desc:
                    return True
                if desc.lower() in {"to"}:
                    return True
                if amount_like.match(desc):
                    return True
            return False

        def _extract_pdf_text_fallback() -> str | None:
            override = getattr(self, "_pdf_text_override", None)
            if isinstance(override, str) and override.strip():
                return override
            pdf_bytes = getattr(self, "_pdf_bytes", None)
            if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes:
                return None
            password = getattr(self, "_pdf_password", None)
            try:
                reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
                if getattr(reader, "is_encrypted", False):
                    reader.decrypt(password or "")
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                return None

        # Primary parse on Unstructured's extracted text.
        transactions = _parse_text_to_transactions(full_text)

        # SBI-specific deterministic fallback: also try plain text extraction using pypdf.
        # Prefer it if:
        # - the current parse is corrupt, OR
        # - it yields strictly more transactions (common when Unstructured drops rows).
        fb_text = _extract_pdf_text_fallback()
        if fb_text:
            fb_txns = _parse_text_to_transactions(fb_text)
            if fb_txns and not _looks_corrupt(fb_txns):
                if _looks_corrupt(transactions) or len(fb_txns) > len(transactions):
                    transactions = fb_txns

        logger.info("Extracted transactions", extra={"transactions_count": len(transactions)})
        return (
            transactions
            if transactions
            else super()._extract_transactions(elements, full_text)
        )

    def _find_statement_period(self, elements: list[Any], full_text: str) -> date:
        """Extract statement period from SBI statement.

        SBI statements typically show:
        - "Statement Date - 15 Jan 2026" (single date, not a range)

        The statement date represents the end of the billing cycle,
        so we use that month as the statement month.

        Args:
            elements: PDF elements
            full_text: Concatenated text

        Returns:
            First day of the statement month

        Raises:
            ValueError: If statement period not found
        """
        logger.debug("Looking for statement period (SBI)")

        # SBI-specific patterns - single statement date
        # Note: OCR may put other text between "Statement Date" and the actual date
        sbi_patterns = [
            r"Statement\s+Date\s*[:\-]?\s*(\d{1,2}\s+\w+\s+\d{4})",  # Statement Date 15 Jan 2026
            r"Statement\s+Date.*?(\d{1,2}\s+\w{3,9}\s+\d{4})",  # Statement Date ... 15 Jan 2026 (with text in between)
            r"Statement\s+Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",  # Statement Date 15/01/2026
        ]

        for i, pattern in enumerate(sbi_patterns):
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                logger.debug("Found statement date (SBI pattern)", extra={"pattern": i + 1})
                statement_date = self._parse_date(date_str)
                result = date(statement_date.year, statement_date.month, 1)
                logger.debug("Derived statement month (SBI)")
                return result

        # Try period range patterns
        period_patterns = [
            r"(?:From|from)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?:to|To)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Statement\s+(?:Period|period)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?:to|To)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Billing\s+(?:Period|period)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?:to|To)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for i, pattern in enumerate(period_patterns):
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # Parse the end date and get the month
                end_date_str = match.group(2)
                logger.debug("Found statement period range (SBI pattern)", extra={"pattern": i + 1})
                end_date = self._parse_date(end_date_str)
                result = date(end_date.year, end_date.month, 1)
                logger.debug("Derived statement month (SBI)")
                return result

        # Fall back to generic patterns
        logger.debug("SBI period patterns failed; trying generic patterns")
        try:
            return super()._find_statement_period(elements, full_text)
        except ValueError:
            raise ValueError("Could not find statement period in SBI statement")
