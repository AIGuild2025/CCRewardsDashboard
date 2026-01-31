"""
DOM Fingerprinting and change detection.

Detects if a page has changed since last scrape without database lookups.
Enables efficient scheduling: only extract data if page content changed.
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class DOMFingerprint:
    """
    Lightweight page fingerprinting using HTML hashing.
    
    Strategy:
    - Hash the first N characters of the HTML (stable DOM slice)
    - Store fingerprints locally or in Redis for fast lookup
    - Compare on each run: if fingerprint differs, page changed
    """
    
    STABLE_SLICE_SIZE = 20000  # First 20KB of HTML usually contains key structure
    FINGERPRINT_CACHE_DIR = Path(os.getenv("FINGERPRINT_CACHE_DIR", "./cache/fingerprints"))
    
    @staticmethod
    def compute(html: str, url: str) -> str:
        """
        Compute fingerprint of a page.
        
        Args:
            html: Full HTML content
            url: Page URL (for context)
        
        Returns:
            SHA256 hash of stable HTML slice
        """
        # Take stable slice from HTML
        stable_slice = html[:DOMFingerprint.STABLE_SLICE_SIZE]
        
        # Hash it
        fingerprint = hashlib.sha256(stable_slice.encode('utf-8', errors='ignore')).hexdigest()
        
        logger.debug(f"Computed fingerprint for {url}: {fingerprint}")
        return fingerprint
    
    @staticmethod
    def has_changed(new_html: str, url: str) -> bool:
        """
        Check if page has changed since last scrape.
        
        Args:
            new_html: Current page HTML
            url: Page URL
        
        Returns:
            True if page changed, False if unchanged
        """
        new_fp = DOMFingerprint.compute(new_html, url)
        old_fp = DOMFingerprint.load(url)
        
        if old_fp is None:
            logger.info(f"No previous fingerprint for {url} (first run)")
            DOMFingerprint.save(url, new_fp)
            return True
        
        changed = new_fp != old_fp
        
        if changed:
            logger.info(f"Page changed for {url}")
            DOMFingerprint.save(url, new_fp)
        else:
            logger.info(f"Page unchanged for {url}")
        
        return changed
    
    @staticmethod
    def save(url: str, fingerprint: str) -> None:
        """
        Save fingerprint to local cache.
        
        Args:
            url: Page URL
            fingerprint: Computed fingerprint
        """
        try:
            DOMFingerprint.FINGERPRINT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Create safe filename from URL
            safe_name = hashlib.sha256(url.encode()).hexdigest()
            cache_file = DOMFingerprint.FINGERPRINT_CACHE_DIR / f"{safe_name}.json"
            
            cache_data = {
                "url": url,
                "fingerprint": fingerprint,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            logger.debug(f"Saved fingerprint for {url}")
        except Exception as e:
            logger.warning(f"Failed to save fingerprint: {e}")
    
    @staticmethod
    def load(url: str) -> Optional[str]:
        """
        Load previous fingerprint from cache.
        
        Args:
            url: Page URL
        
        Returns:
            Previous fingerprint or None if not found
        """
        try:
            safe_name = hashlib.sha256(url.encode()).hexdigest()
            cache_file = DOMFingerprint.FINGERPRINT_CACHE_DIR / f"{safe_name}.json"
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            return data.get("fingerprint")
        except Exception as e:
            logger.warning(f"Failed to load fingerprint: {e}")
            return None


def is_page_changed(page_content) -> bool:
    """
    Convenience function to check if page changed.
    
    Args:
        page_content: PageContent object from fetcher
    
    Returns:
        True if page changed since last scrape
    """
    return DOMFingerprint.has_changed(page_content.html, page_content.url)


def get_dom_diff(old_html: str, new_html: str) -> Dict[str, Any]:
    """
    Calculate percentage of DOM that changed.
    
    Simple heuristic: compare lengths and key structure markers.
    For more sophisticated diffing, consider difflib or specialized DOM diff libraries.
    
    Args:
        old_html: Previous HTML
        new_html: Current HTML
    
    Returns:
        Dictionary with diff metrics
    """
    old_lines = set(old_html.split('\n'))
    new_lines = set(new_html.split('\n'))
    
    changed_lines = len(old_lines.symmetric_difference(new_lines))
    total_lines = len(old_lines.union(new_lines))
    
    diff_percentage = (changed_lines / max(total_lines, 1)) * 100
    
    return {
        "diff_percentage": diff_percentage,
        "changed_lines": changed_lines,
        "total_lines": total_lines,
        "size_old": len(old_html),
        "size_new": len(new_html)
    }


# Lazy import to avoid circular dependency
from datetime import datetime
