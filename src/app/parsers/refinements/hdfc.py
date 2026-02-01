"""HDFC Bank parser refinement.

Overrides date parsing to handle HDFC's DD-MMM-YY format.
"""

import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from itertools import permutations
from typing import Any

from app.parsers.generic import GenericParser
from app.schemas.internal import ParsedAccountSummary
from app.schemas.internal import ParsedTransaction


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
        self._account_summary: ParsedAccountSummary | None = None
        self._reward_points_earned: int = 0
        self._reward_points_previous: int | None = None
        self._reward_points_redeemed: int | None = None

    def parse(self, elements: list[Any]):
        """Override parse to extract Account Summary (when present).

        For HDFC statements, the Account Summary 'Total Dues' is treated as the
        authoritative outstanding amount.
        """
        full_text = "\n".join(str(element) for element in elements)
        self._account_summary = self._find_account_summary(elements, full_text)

        # Initialize reward summary trackers (populated by _find_rewards when possible).
        self._reward_points_earned = 0
        self._reward_points_previous = None
        self._reward_points_redeemed = None

        parsed = super().parse(elements)
        parsed.account_summary = self._account_summary
        if parsed.account_summary is not None:
            parsed.closing_balance_cents = parsed.account_summary.total_outstanding_cents

        parsed.reward_points_earned = self._reward_points_earned
        parsed.reward_points_previous = self._reward_points_previous
        parsed.reward_points_redeemed = self._reward_points_redeemed
        return parsed

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

        # Fallback to GenericParser formats
        return super()._parse_date(text)

    def _find_closing_balance(self, elements: list[Any], full_text: str) -> int:
        """Prefer Account Summary 'Total Dues' as outstanding when available."""
        if self._account_summary is not None:
            return self._account_summary.total_outstanding_cents
        return super()._find_closing_balance(elements, full_text)

    def _find_rewards(self, elements: list[Any], full_text: str) -> int:
        """Extract HDFC reward points closing balance and earned this period.

        HDFC often includes a "Reward Points Summary" table with columns like:
          - Opening Balance
          - Feature + Bonus Reward Points Earned
          - Disbursed
          - Adjusted/Lapsed
          - Closing Balance
          - Points expiring in next 30/60 days

        We store:
          - reward_points: Closing Balance (total points balance)
          - reward_points_earned: Earned this period
          - reward_points_previous: Opening Balance
          - reward_points_redeemed: Disbursed + Adjusted/Lapsed (if present)
        """

        def _to_int(raw: str) -> int:
            return int(raw.replace(",", "").strip())

        normalized = re.sub(r"\s+", " ", full_text)
        lower = normalized.lower()
        idx = lower.find("reward points summary")
        if idx < 0:
            # Newer HDFC template prints a "Reward Points" label near the top,
            # followed by the current points balance (closing).
            m_close = re.search(r"(?i)\breward\s+points\b\s*([\d,]{1,8})", full_text)
            closing_alt: int | None = None
            if m_close:
                try:
                    closing_alt = _to_int(m_close.group(1))
                except Exception:
                    closing_alt = None

            if closing_alt is None:
                return super()._find_rewards(elements, full_text)

            # If present, parse the 4-number row: opening, earned, disbursed, adjusted.
            # Closing is provided by the "Reward Points" label above.
            window = full_text[m_close.start() : min(len(full_text), m_close.start() + 1000)]
            win_norm = re.sub(r"\s+", " ", window)
            row = re.search(
                r"(?i)\bopening\s+balance\b.*?\badjusted\s*/\s*lapsed\b\s*"
                r"(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\b",
                win_norm,
            )
            if row:
                opening_alt = _to_int(row.group(1))
                earned_alt = _to_int(row.group(2))
                disb_alt = _to_int(row.group(3))
                adj_alt = _to_int(row.group(4))
                self._reward_points_previous = opening_alt
                self._reward_points_earned = earned_alt
                self._reward_points_redeemed = disb_alt + adj_alt
            else:
                self._reward_points_previous = None
                self._reward_points_earned = 0
                self._reward_points_redeemed = None

            return closing_alt

        section = normalized[idx : min(len(normalized), idx + 2200)]

        def _grab(pattern: str) -> int | None:
            m = re.search(pattern, section, re.IGNORECASE)
            if not m:
                return None
            try:
                return _to_int(m.group(1))
            except Exception:
                return None

        opening = _grab(r"\bopening\s+balance\s+(\d[\d,]*)\b")
        earned = _grab(
            r"\b(?:feature\s*\+\s*bonus\s+)?reward\s+points\s+earned\s+(\d[\d,]*)\b"
        )
        disbursed = _grab(r"\bdisbursed\s+(\d[\d,]*)\b")
        adjusted = _grab(r"\badjusted\s*/\s*lapsed\s+(\d[\d,]*)\b")
        closing = _grab(r"\bclosing\s+balance\s+(\d[\d,]*)\b")

        if closing is not None:
            self._reward_points_previous = opening
            if earned is not None:
                self._reward_points_earned = earned
            redeemed = None
            if disbursed is not None or adjusted is not None:
                redeemed = (disbursed or 0) + (adjusted or 0)
            self._reward_points_redeemed = redeemed

            # Derive earned if missing but other parts exist.
            if earned is None and opening is not None and redeemed is not None:
                self._reward_points_earned = max(0, closing - opening + redeemed)
            return closing

        # Fallback: look for a 5-number row and assign by invariant:
        #   opening + earned - disbursed - adjusted == closing
        # This handles cases where numbers appear without labels or are reordered.
        section_no_commas = section.replace(",", "")
        five_num_pattern = r"(\d{1,7})\s+(\d{1,7})\s+(\d{1,7})\s+(\d{1,7})\s+(\d{1,7})"

        def _score(nums: list[int], cand: tuple[int, int, int, int, int]) -> tuple[int, int, int]:
            prev, earn, disb, adj, close = cand
            penalty = 0
            min_val = min(nums)
            max_val = max(nums)
            if close == min_val:
                penalty += 1000
            if close < prev:
                penalty += 200
            if earn > prev:
                penalty += 100
            # Prefer small disb/adj (often 0)
            penalty += disb + adj
            # Prefer closing being the largest
            penalty += 0 if close == max_val else 5
            return (penalty, disb + adj, -close)

        best: tuple[tuple[int, int, int, int, int], tuple[int, int, int]] | None = None

        for m in re.finditer(five_num_pattern, section_no_commas):
            raw = [int(g) for g in m.groups()]
            nums = list(raw)
            # Try all assignments; duplicates are fine.
            for a in permutations(range(5), 5):
                prev, earn, disb, adj, close = (
                    nums[a[0]],
                    nums[a[1]],
                    nums[a[2]],
                    nums[a[3]],
                    nums[a[4]],
                )
                if prev + earn - disb - adj != close:
                    continue
                cand = (prev, earn, disb, adj, close)
                score = _score(nums, cand)
                if best is None or score < best[1]:
                    best = (cand, score)

        if best is None:
            return super()._find_rewards(elements, full_text)

        prev, earn, disb, adj, close = best[0]
        self._reward_points_previous = prev
        self._reward_points_earned = earn
        self._reward_points_redeemed = disb + adj
        return close

    def _find_account_summary(
        self, elements: list[Any], full_text: str
    ) -> ParsedAccountSummary | None:
        """Extract HDFC 'Account Summary' table (amounts in minor units).

        Expected columns:
          - Opening Balance
          - Payment/Credits
          - Purchase/Debits
          - Finance Charges
          - Total Dues

        Returns:
            ParsedAccountSummary if found, otherwise None.
        """

        def _money_to_cents(raw: str) -> int | None:
            s = raw.strip().replace(",", "")
            if not s:
                return None
            try:
                return int(Decimal(s) * 100)
            except (InvalidOperation, ValueError):
                return None

        def _from_text(text: str) -> ParsedAccountSummary | None:
            normalized = re.sub(r"\s+", " ", text)
            lower = normalized.lower()
            idx = lower.find("account summary")
            if idx < 0:
                return None

            # Keep a bounded window to avoid matching unrelated 5-number runs.
            section = normalized[idx : min(len(normalized), idx + 2200)]
            if not (
                ("opening" in section.lower())
                and ("total" in section.lower())
                and ("dues" in section.lower())
            ):
                return None

            amount_pat = r"(\d[\d,]*\.\d{2})"
            five_amounts_pat = (
                rf"{amount_pat}\s+{amount_pat}\s+{amount_pat}\s+{amount_pat}\s+{amount_pat}"
            )

            def _delta(
                previous: int, credits: int, debits: int, fees: int, outstanding: int
            ) -> int:
                return (previous - credits + debits + fees) - outstanding

            def _heuristic_penalty(nums: list[int], cand: tuple[int, int, int, int, int]) -> int:
                previous, credits, debits, fees, outstanding = cand
                sorted_nums = sorted(nums)
                smallest_two = set(sorted_nums[:2])

                penalty = 0
                # Fees are often small (including 0.00).
                if fees not in smallest_two:
                    penalty += 10
                # Outstanding is usually among the largest values.
                if outstanding in smallest_two:
                    penalty += 25
                # Credits are frequently small (often 0), but shouldn't exceed outstanding.
                if credits > outstanding:
                    penalty += 25
                # Prefer outstanding close to debits when opening/credits/fees are small.
                penalty += min(abs(outstanding - debits) // 100, 50)
                return penalty

            best: tuple[int, int, tuple[int, int, int, int, int]] | None = None
            max_abs_delta = 250  # 2.50 (paise/cents) tolerance for rounding

            for match in re.finditer(five_amounts_pat, section):
                raw_nums = list(match.groups())
                cents = [_money_to_cents(v) for v in raw_nums]
                if any(v is None for v in cents):
                    continue
                nums = [int(v) for v in cents if v is not None]
                if len(nums) != 5:
                    continue

                # Prefer the natural column order first.
                ordered = (nums[0], nums[1], nums[2], nums[3], nums[4])
                d = _delta(*ordered)
                if abs(d) <= max_abs_delta:
                    cand = (abs(d), _heuristic_penalty(nums, ordered), ordered)
                    best = cand if best is None or cand[:2] < best[:2] else best

                # Also allow reordered extractions.
                for idxs in permutations(range(5), 5):
                    cand_vals = (
                        nums[idxs[0]],
                        nums[idxs[1]],
                        nums[idxs[2]],
                        nums[idxs[3]],
                        nums[idxs[4]],
                    )
                    d = _delta(*cand_vals)
                    if abs(d) > max_abs_delta:
                        continue
                    cand = (abs(d), _heuristic_penalty(nums, cand_vals), cand_vals)
                    best = cand if best is None or cand[:2] < best[:2] else best

            if best is None:
                return None

            _, _, (previous, credits, debits, fees, outstanding) = best
            return ParsedAccountSummary(
                previous_balance_cents=previous,
                credits_cents=credits,
                debits_cents=debits,
                fees_cents=fees,
                total_outstanding_cents=outstanding,
            )

        parsed = _from_text(full_text)
        if parsed is not None:
            return parsed

        # Some PDFs extract poorly via Unstructured; fall back to pypdf if available.
        pdf_bytes = getattr(self, "_pdf_bytes", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)):
            return None

        password = getattr(self, "_pdf_password", None)
        normalized_password = password.strip() if isinstance(password, str) else None
        if normalized_password == "":
            normalized_password = None

        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
            if getattr(reader, "is_encrypted", False):
                ok = reader.decrypt(normalized_password or "")
                if not ok:
                    return None

            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return None

        return _from_text(extracted)

    def _extract_transactions(
        self, elements: list[Any], full_text: str
    ) -> list[ParsedTransaction]:
        """Extract transactions from HDFC statement sections.

        HDFC tables like "Domestic Transactions" often get extracted as
        column-wise lines (date/time, description, points, amount on separate lines).
        Generic regex-based extraction can undercount in those cases.
        """

        def _is_section_end(line: str) -> bool:
            up = line.strip().upper()
            return (
                up.startswith("REWARD POINTS SUMMARY")
                or up.startswith("REWARDS PROGRAM")
                or up.startswith("OFFERS ON YOUR CREDIT CARD")
                or up.startswith("IMPORTANT INFORMATION")
                or up.startswith("PAGE ")
                or up.startswith("MONEYBACK CREDIT CARD STATEMENT")
            )

        def _parse_section(text: str, heading: str) -> list[ParsedTransaction]:
            lower = text.lower()
            idx = lower.find(heading.lower())
            if idx < 0:
                return []

            # Bounded window: keep just the section that contains rows.
            section = text[idx : min(len(text), idx + 5000)]
            lines = [ln.strip() for ln in section.splitlines() if ln.strip()]

            # Skip header lines until we see the column header "Date".
            start_at = 0
            for i, ln in enumerate(lines):
                if ln.strip().lower().startswith("date"):
                    start_at = i + 1
                    break

            # Collect only the data-ish lines for this section (bounded by the next section).
            data_lines: list[str] = []
            for ln in lines[start_at:]:
                # Stop if the next section begins.
                if heading.lower().startswith("domestic") and ln.strip().lower().startswith(
                    "international transactions"
                ):
                    break
                if heading.lower().startswith("international") and ln.strip().lower().startswith(
                    "domestic transactions"
                ):
                    break

                if _is_section_end(ln):
                    break

                data_lines.append(ln)

            # Transaction start: DD/MM/YYYY [HH:MM[:SS]] (time may be separated by a "|")
            start_only_re = re.compile(
                r"^\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})"
                r"(?:\s*(?:\||\s)\s*(\d{1,2}:\d{2}(?::\d{2})?))?\s*$"
            )
            start_inline_re = re.compile(
                r"^\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})"
                r"(?:\s*(?:\||\s)\s*(\d{1,2}:\d{2}(?::\d{2})?))?\s+(.+?)\s*$"
            )
            amount_re = re.compile(r"^[₹$C]?\s*[\d,]+\.\d{2}\s*$")
            points_re = re.compile(r"^\d{1,5}$")
            trailing_points_re = re.compile(r"^(.*?)(?:\s+\d{1,5})\s*$")
            trailing_amount_re = re.compile(r"^(.*?)([₹$C]?\s*[\d,]+\.\d{2})\s*$")
            trailing_pi_re = re.compile(r"^(.*?)(?:\s+\b[a-zA-Z]\b)\s*$")

            txns: list[ParsedTransaction] = []
            current_date: date | None = None
            current_desc_parts: list[str] = []
            current_amount: int | None = None

            def _flush() -> None:
                nonlocal current_date, current_desc_parts, current_amount
                if current_date is None or current_amount is None:
                    current_date = None
                    current_desc_parts = []
                    current_amount = None
                    return

                desc = " ".join(p for p in current_desc_parts if p).strip()
                desc = re.sub(r"\s+", " ", desc)
                if not desc:
                    desc = "Unknown"

                lowered = desc.lower()
                txn_type = "debit"
                if "refund" in lowered or "reversal" in lowered or "credit" in lowered:
                    txn_type = "credit"

                txns.append(
                    ParsedTransaction(
                        transaction_date=current_date,
                        description=desc,
                        amount_cents=current_amount,
                        transaction_type=txn_type,
                    )
                )

                current_date = None
                current_desc_parts = []
                current_amount = None

            for ln in data_lines:
                # New transaction starts with a date/time line (sometimes inline with description/amount).
                m_inline = start_inline_re.match(ln)
                if m_inline:
                    _flush()
                    try:
                        current_date = self._parse_date(m_inline.group(1))
                    except Exception:
                        current_date = None
                    tail = m_inline.group(3).strip()
                    # Some formats include a trailing "PI" marker column (single-letter).
                    m_pi = trailing_pi_re.match(tail)
                    if m_pi:
                        tail = m_pi.group(1).strip()
                    # Some formats include reward points as "+ 4" or just "+" (not part of merchant).
                    tail = re.sub(r"\+\s*(?:\d{1,5})?\b", " ", tail).strip()
                    # If the line ends with an amount, parse and flush immediately.
                    m_amt = trailing_amount_re.match(tail)
                    if m_amt:
                        maybe_desc = m_amt.group(1).strip()
                        amt_text = m_amt.group(2).strip()
                        # Strip trailing points if present in the inline description.
                        m_pts = trailing_points_re.match(maybe_desc)
                        if m_pts:
                            maybe_desc = m_pts.group(1).strip()
                        if maybe_desc:
                            current_desc_parts.append(maybe_desc)
                        try:
                            amt = self._parse_amount(amt_text)
                            current_amount = abs(int(amt * 100))
                        except Exception:
                            current_amount = None
                        _flush()
                    else:
                        # Otherwise treat remainder as first description fragment.
                        if tail and not points_re.match(tail) and not amount_re.match(tail):
                            current_desc_parts.append(tail)
                    continue

                m_only = start_only_re.match(ln)
                if m_only:
                    _flush()
                    try:
                        current_date = self._parse_date(m_only.group(1))
                    except Exception:
                        current_date = None
                    continue

                if current_date is None:
                    # Ignore preamble lines until first transaction date.
                    continue

                # Some statements split a single transaction across multiple lines,
                # where the amount appears on a later line together with extra text.
                ln_clean = ln.strip()
                m_pi2 = trailing_pi_re.match(ln_clean)
                if m_pi2:
                    ln_clean = m_pi2.group(1).strip()
                ln_clean = re.sub(r"\+\s*(?:\d{1,5})?\b", " ", ln_clean).strip()

                m_tail_amt = trailing_amount_re.match(ln_clean)
                if m_tail_amt:
                    maybe_desc = m_tail_amt.group(1).strip()
                    amt_text = m_tail_amt.group(2).strip()
                    m_pts = trailing_points_re.match(maybe_desc)
                    if m_pts:
                        maybe_desc = m_pts.group(1).strip()
                    if maybe_desc and not points_re.match(maybe_desc):
                        current_desc_parts.append(maybe_desc)
                    try:
                        amt = self._parse_amount(amt_text)
                        current_amount = abs(int(amt * 100))
                    except Exception:
                        current_amount = None
                    _flush()
                    continue

                # Amount often appears as its own line.
                if amount_re.match(ln):
                    try:
                        amt = self._parse_amount(ln)
                        current_amount = abs(int(amt * 100))
                    except Exception:
                        pass
                    _flush()
                    continue

                # Reward points column often appears as a bare integer line.
                if points_re.match(ln):
                    continue

                # Otherwise treat as part of description.
                current_desc_parts.append(ln)

            _flush()

            # If line-based parsing undercounts (common when pypdf reorders columns),
            # fall back to a regex scan over the section body.
            body_text = "\n".join(data_lines)
            date_anywhere_re = re.compile(r"(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})")
            date_count = len(date_anywhere_re.findall(body_text))
            if date_count > 0 and len(txns) < max(1, min(2, date_count)):
                # Split the body into chunks starting at each date occurrence.
                starts = list(date_anywhere_re.finditer(body_text))
                chunks: list[str] = []
                for i, m in enumerate(starts):
                    start = m.start()
                    end = starts[i + 1].start() if i + 1 < len(starts) else len(body_text)
                    chunks.append(body_text[start:end])

                parsed: list[ParsedTransaction] = []
                head_re = re.compile(
                    r"^\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})(?:\s*(?:\||\s)\s*(\d{1,2}:\d{2}(?::\d{2})?))?\s*",
                    flags=re.DOTALL,
                )
                money_re = re.compile(r"([₹$C]?\s*[\d,]+\.\d{2})")

                for chunk in chunks:
                    hm = head_re.match(chunk)
                    if not hm:
                        continue
                    date_str = hm.group(1)
                    try:
                        txn_date = self._parse_date(date_str)
                    except Exception:
                        continue

                    amounts = money_re.findall(chunk)
                    if not amounts:
                        continue
                    amt_text = amounts[-1]
                    try:
                        amt = self._parse_amount(amt_text)
                        amount_cents = abs(int(amt * 100))
                    except Exception:
                        continue

                    desc = chunk[hm.end() :]
                    # Remove the amount token and any trailing points integers.
                    desc = desc.replace(amt_text, " ")
                    desc = re.sub(r"\b\d{1,5}\b", " ", desc)
                    desc = re.sub(r"\s+", " ", desc).strip()

                    # Drop obvious header noise if it got merged into the chunk.
                    desc = re.sub(
                        r"(?i)\b(date|transaction description|feature reward points|amount\s*\(in\s*rs\.\))\b",
                        " ",
                        desc,
                    )
                    desc = re.sub(r"\s+", " ", desc).strip()
                    if not desc:
                        desc = "Unknown"

                    lowered = desc.lower()
                    txn_type = "debit"
                    if "refund" in lowered or "reversal" in lowered or "credit" in lowered:
                        txn_type = "credit"

                    parsed.append(
                        ParsedTransaction(
                            transaction_date=txn_date,
                            description=desc,
                            amount_cents=amount_cents,
                            transaction_type=txn_type,
                        )
                    )

                if parsed:
                    # De-dup exact matches (in case both strategies catch some rows).
                    seen: set[tuple[date, str, int, str]] = set()
                    uniq: list[ParsedTransaction] = []
                    for t in parsed:
                        key = (t.transaction_date, t.description, t.amount_cents, t.transaction_type)
                        if key in seen:
                            continue
                        seen.add(key)
                        uniq.append(t)
                    return uniq

            return txns

        # First try section-based parsing on the extracted full text.
        txns = []
        txns.extend(_parse_section(full_text, "Domestic Transactions"))
        txns.extend(_parse_section(full_text, "International Transactions"))

        # Fallback: if section parsing found nothing, use GenericParser logic.
        if not txns:
            return super()._extract_transactions(elements, full_text)

        return txns

    def _find_statement_period(self, elements: list[Any], full_text: str) -> date:
        """Derive statement month from HDFC's 'Statement Date' when no range is present."""
        def _try_text(text: str) -> date | None:
            match = re.search(
                r"(?i)\bStatement\s+Date\s*:\s*(\d{1,2}[-/\.]\w{1,9}[-/\.]\d{2,4})",
                text,
            )
            if not match:
                return None
            d = self._parse_date(match.group(1))
            return date(d.year, d.month, 1)

        derived = _try_text(full_text)
        if derived is not None:
            return derived

        # Some PDFs extract poorly via Unstructured; fall back to pypdf if available.
        pdf_bytes = getattr(self, "_pdf_bytes", None)
        if isinstance(pdf_bytes, (bytes, bytearray)):
            password = getattr(self, "_pdf_password", None)
            normalized_password = password.strip() if isinstance(password, str) else None
            if normalized_password == "":
                normalized_password = None
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
                if getattr(reader, "is_encrypted", False):
                    ok = reader.decrypt(normalized_password or "")
                    if not ok:
                        reader = None
                if reader is not None:
                    extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
                    derived = _try_text(extracted)
                    if derived is not None:
                        return derived
            except Exception:
                pass

        return super()._find_statement_period(elements, full_text)

    def _find_card_number(self, elements: list[Any], full_text: str) -> str:
        """Extract last 4 digits of card number from HDFC statements.

        HDFC often formats this line as:
        - "Card No: 4893XXXXXXXXXX3777"
        - "Card No: 4893 XXXX XXXX 3777"
        - "Card No: XXXX XXXX XXXX 3777"
        """
        def _try_text(text: str) -> str | None:
            match = re.search(r"(?i)\bCard\s*No\s*:\s*([0-9Xx*\s]{8,30})", text)
            if not match:
                return None
            raw = match.group(1)
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 4:
                return digits[-4:]
            return None

        last4 = _try_text(full_text)
        if last4 is not None:
            return last4

        # Some PDFs extract poorly via Unstructured; fall back to pypdf if available.
        pdf_bytes = getattr(self, "_pdf_bytes", None)
        if isinstance(pdf_bytes, (bytes, bytearray)):
            password = getattr(self, "_pdf_password", None)
            normalized_password = password.strip() if isinstance(password, str) else None
            if normalized_password == "":
                normalized_password = None
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(bytes(pdf_bytes)))
                if getattr(reader, "is_encrypted", False):
                    ok = reader.decrypt(normalized_password or "")
                    if not ok:
                        reader = None
                if reader is not None:
                    extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
                    last4 = _try_text(extracted)
                    if last4 is not None:
                        return last4
            except Exception:
                pass

        # Fall back to generic patterns/heuristics.
        return super()._find_card_number(elements, full_text)
