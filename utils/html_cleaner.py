"""
HTML cleaning and normalization utilities.
"""

import re
from html import unescape
import logging

logger = logging.getLogger(__name__)


def clean_html(html: str) -> str:
    """
    Clean HTML for better text extraction.
    
    - Remove scripts and styles
    - Remove comments
    - Normalize whitespace
    """
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove comments
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    # Remove excessive whitespace
    html = re.sub(r'\s+', ' ', html)
    
    # Decode HTML entities
    html = unescape(html)
    
    return html


def extract_text_blocks(html: str, min_length: int = 20) -> list[str]:
    """
    Extract text blocks from HTML.
    
    Args:
        html: HTML content
        min_length: Minimum block length to include
    
    Returns:
        List of text blocks
    """
    # Remove tags
    text = re.sub(r'<[^>]+>', '\n', html)
    
    # Split by newlines and filter
    blocks = [line.strip() for line in text.split('\n')]
    blocks = [b for b in blocks if len(b) >= min_length]
    
    return blocks


def sanitize_for_db(text: str) -> str:
    """
    Sanitize text for database storage.
    
    - Remove null bytes
    - Normalize line endings
    - Truncate if too long
    """
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    return text
