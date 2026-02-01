"""Bank metadata helpers (UI-friendly)."""

from __future__ import annotations

from typing import Final

BANK_LOGO_URLS: Final[dict[str, str]] = {
    "hdfc": "/static/banks/hdfc.svg",
}


def get_bank_logo_url(bank_code: str | None) -> str | None:
    if not bank_code:
        return None
    return BANK_LOGO_URLS.get(bank_code.strip().lower())

