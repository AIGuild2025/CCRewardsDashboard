"""Transaction categorization utilities.

This module provides deterministic, local categorization of transactions based on
their descriptions. It is intentionally rule-based (no network calls) to keep
ingestion fast and privacy-safe.
"""

from .rules import categorize

__all__ = ["categorize"]
