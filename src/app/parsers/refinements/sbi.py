"""SBI Bank parser refinement.

Overrides card number detection and date parsing to handle SBI's formats.
"""

import re
from datetime import date, datetime
from itertools import permutations
from typing import Any

from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedTransaction


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
        print("[SBI PARSER] Attempting to find card number...")
        # Try SBI-specific patterns first
        for i, pattern in enumerate(self.SBI_CARD_PATTERNS):
            match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                digits = match.group(1)
                # If only 2 digits found, pad with XX prefix
                if len(digits) == 2:
                    result = f"XX{digits}"
                    print(f"[SBI PARSER] Found card number: {result} (pattern {i+1})")
                    return result
                print(f"[SBI PARSER] Found card number: {digits} (pattern {i+1})")
                return digits

        # Fall back to generic patterns
        print("[SBI PARSER] SBI patterns failed, trying generic patterns...")
        try:
            result = super()._find_card_number(elements, full_text)
            print(f"[SBI PARSER] Found via generic: {result}")
            return result
        except ValueError:
            # If still not found, show sample text for debugging
            sample = full_text[:500] if len(full_text) > 500 else full_text
            print(f"[SBI PARSER] Card number not found. Sample text:\n{sample}")
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
        print("[SBI PARSER] Extracting reward points...")

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
            print(
                "[SBI PARSER] Reward points found via invariant: "
                f"Previous={previous}, Earned={earned}, Redeemed={redeemed}, Closing={closing}"
            )
            self._reward_points_earned = earned
            return closing

        print("[SBI PARSER] Reward points not found, defaulting to 0")
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
        print("[SBI PARSER] Extracting transactions...")
        transactions = []

        # Pattern: DD MMM YY MERCHANT... AMOUNT C/D
        # The merchant name can span multiple words/lines
        pattern = r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([CD])"

        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            try:
                date_str = match.group(1)  # "15 Dec 25"
                merchant = match.group(2).strip()  # "APOLLO PHARMACIES LIMI IN"
                amount_str = match.group(3).replace(",", "")  # "1138.82"
                txn_type = match.group(4)  # "C" or "D"

                # Parse date
                txn_date = self._parse_date(date_str)

                # Parse amount
                amount_cents = int(float(amount_str) * 100)

                # Determine transaction type
                transaction_type = 'credit' if txn_type.upper() == 'C' else 'debit'

                transaction = ParsedTransaction(
                    transaction_date=txn_date,
                    description=merchant,
                    amount_cents=amount_cents,
                    transaction_type=transaction_type,
                    category=None  # SBI doesn't provide category
                )
                transactions.append(transaction)

            except Exception as e:
                print(
                    f"[SBI PARSER] Failed to parse transaction: {match.group(0)[:50]} - {e}"
                )
                continue

        print(f"[SBI PARSER] Extracted {len(transactions)} transactions")
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
        print("[SBI PARSER] Looking for statement period...")

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
                print(f"[SBI PARSER] Found statement date (pattern {i+1}): {date_str}")
                statement_date = self._parse_date(date_str)
                result = date(statement_date.year, statement_date.month, 1)
                print(f"[SBI PARSER] Statement month: {result}")
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
                print(
                    f"[SBI PARSER] Found period (pattern {i+1}): {match.group(1)} to {end_date_str}"
                )
                end_date = self._parse_date(end_date_str)
                result = date(end_date.year, end_date.month, 1)
                print(f"[SBI PARSER] Statement month: {result}")
                return result

        # Fall back to generic patterns
        print("[SBI PARSER] SBI period patterns failed, trying generic...")
        try:
            return super()._find_statement_period(elements, full_text)
        except ValueError:
            # Show sample text for debugging
            sample = full_text[:1000] if len(full_text) > 1000 else full_text
            print(f"[SBI PARSER] Statement period not found. Sample text:\n{sample}")
            raise ValueError("Could not find statement period in SBI statement")
