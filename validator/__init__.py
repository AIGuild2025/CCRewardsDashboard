"""
Validator module initialization.
"""

from validator.dom_fingerprint import DOMFingerprint, is_page_changed, get_dom_diff

__all__ = ["DOMFingerprint", "is_page_changed", "get_dom_diff"]
