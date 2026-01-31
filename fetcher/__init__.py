"""
Fetcher module initialization.
"""

from fetcher.page_loader import load_page, PageContent, PlaywrightClient, extract_meta_tags

__all__ = ["load_page", "PageContent", "PlaywrightClient", "extract_meta_tags"]
