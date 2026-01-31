"""
Utils module initialization.
"""

from utils.logger import setup_logging
from utils.html_cleaner import clean_html, extract_text_blocks, sanitize_for_db
from utils.confidence import calculate_field_confidence, scale_confidence

__all__ = [
    "setup_logging",
    "clean_html",
    "extract_text_blocks",
    "sanitize_for_db",
    "calculate_field_confidence",
    "scale_confidence"
]
