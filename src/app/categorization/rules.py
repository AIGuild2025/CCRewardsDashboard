"""Deterministic transaction categorization.

Banks (e.g., SBI) often don't provide a category/MCC in statements. For dashboard
and reward-optimization workflows, we infer a category from the transaction
"description" plus debit/credit direction.

This is intentionally rule-based so it's:
- fast (no external calls)
- explainable (auditable)
- privacy-safe (can run pre/post masking)

Over time, we can refine rules and/or add a user-specific merchant->category
override table.
"""

from __future__ import annotations

import re

# Public taxonomy (can be refined over time).
CATEGORIES: set[str] = {
    "food",
    "shopping",
    "personal_care",
    "fuel",
    "travel",
    "utilities",
    "entertainment",
    "health",
    "fees",
    "transfer",
    "payment",
    "other",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().upper())

def normalize_merchant(description: str | None) -> str:
    """Normalize a merchant/description string into a stable key.

    This is an exact-match key (not fuzzy matching). It is used for fast
    rollups and user-specific category overrides.
    """
    return _norm(description or "")


# Ordering matters: earlier matches win.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    # Payments / transfers / fees (often credits, but not always)
    ("payment", re.compile(r"\bPAYMENT\b|\bPAYMENT\s+RECEIVED\b|\bCC\s+PAYMENT\b")),
    ("fees", re.compile(r"\bFEE\b|\bCHARGE\b|\bSURCHARGE\b|\bGST\b|\bTAX\b|\bLATE\b|\bANNUAL\b|\bWAIVER\b")),

    # Merchant/vertical hints
    ("fuel", re.compile(r"\bFUEL(?:S)?\b|\bPETROL\b|\bDIESEL\b|\bSHELL\b|\bHPCL\b|\bIOCL\b|\bBPCL\b")),
    ("health", re.compile(r"\bPHARM\b|\bPHARMACY\b|\bHOSP\b|\bHOSPITAL\b|\bCLINIC\b|\bMED\b|\bAPOLLO\b")),
    ("personal_care", re.compile(r"\bSALON\b|\bBARBER\b|\bPARLOUR\b|\bPARLOR\b")),
    # Common large merchants (keep narrow; user overrides can still take precedence).
    ("travel", re.compile(r"CLEARTRIP")),
    ("shopping", re.compile(r"RELIANCE\s*RETAIL(?:\s*(?:LTD|LIMITED))?")),
    ("utilities", re.compile(r"\bELECTRIC\b|\bWATER\b|\bGAS\b|\bBROADBAND\b|\bINTERNET\b|\bMOBILE\b|\bRECHARGE\b|\bUTILITY\b")),
    ("travel", re.compile(r"\bIRCTC\b|\bAIR\b|\bAIRLINE\b|\bHOTEL\b|\bUBER\b|\bOLA\b|\bTERMINAL\b|\bTRAVEL\b")),
    ("entertainment", re.compile(r"\bNETFLIX\b|\bSPOTIFY\b|\bPRIME\b|\bHOTSTAR\b|\bAPPLE\s+SERVICES\b|\bGOOGLE\b|\bYOUTUBE\b")),
    ("food", re.compile(r"\bSWIGGY\b|\bZOMATO\b|\bSTARBUCKS\b|\bCAFE\b|\bRESTAURANT\b|\bBAKERY\b|\bFOODS?\b")),
    ("shopping", re.compile(r"\bAMAZON\b|\bFLIPKART\b|\bMYNTRA\b|\bSHOP\b|\bSTORE\b|\bMART\b")),

    # Bank transfer rails. Put this late so merchant hints win (e.g., UPI-Apple Services).
    # Note: UPI is a payment rail used for most card spends in SBI statements, so
    # treating it as "transfer" creates a lot of false positives.
    ("transfer", re.compile(r"\bIMPS\b|\bNEFT\b|\bRTGS\b|\bTRANSFER\b")),
]


def categorize(description: str | None, transaction_type: str | None = None) -> str:
    """Infer a category from the transaction description.

    Args:
        description: Raw or masked merchant/description text.
        transaction_type: "debit" or "credit" when available.

    Returns:
        Category string from the CATEGORIES taxonomy.
    """

    text = _norm(description or "")
    if not text:
        return "other"

    # Credits are often payments/refunds/transfers. If we can't identify them,
    # default to "payment" (useful for spend summaries).
    txn_type = (transaction_type or "").strip().lower()

    for category, pattern in _RULES:
        if pattern.search(text):
            return category

    if txn_type == "credit":
        return "payment"

    return "other"
