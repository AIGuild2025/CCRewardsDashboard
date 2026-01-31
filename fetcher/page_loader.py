"""
Playwright-based page loading and browser lifecycle management.

Handles:
- Browser initialization and cleanup
- JavaScript rendering (networkidle, DOM settle)
- Full page content extraction (HTML + text)
- Screenshot capture on errors
- Timeout and retry logic
"""

import os
import time
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PageContent(BaseModel):
    """Structured page content from Playwright."""
    html: str
    text: str
    url: str
    title: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    screenshot_path: Optional[str] = None
    load_time_ms: float = 0.0


class PlaywrightClient:
    """Manages Playwright browser lifecycle."""
    
    def __init__(self, headless: bool = True, timeout_ms: int = 60000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.playwright = None
        self.browser = None
        self.screenshot_dir = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
    def launch(self) -> None:
        """Launch Playwright browser."""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            logger.info("Playwright browser launched successfully")
        except Exception as e:
            logger.error(f"Failed to launch Playwright: {e}")
            raise
    
    def close(self) -> None:
        """Close browser and cleanup."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Playwright browser closed")
    
    def __enter__(self):
        self.launch()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def load_page(
    url: str,
    headless: bool = True,
    timeout_ms: int = 60000,
    wait_for_state: str = "networkidle",
    scroll_to_bottom: bool = True,
    screenshot_on_error: bool = True
) -> PageContent:
    """
    Load a page using Playwright and extract full content.
    
    Args:
        url: The URL to load
        headless: Whether to run in headless mode
        timeout_ms: Timeout in milliseconds
        wait_for_state: State to wait for ('load', 'domcontentloaded', 'networkidle')
        scroll_to_bottom: Whether to scroll to bottom (loads lazy content)
        screenshot_on_error: Whether to save screenshot on error
    
    Returns:
        PageContent object with HTML, text, and metadata
    
    Raises:
        PlaywrightTimeoutError: If page load times out
        Exception: On other errors
    """
    start_time = time.time()
    page_obj = None
    browser_obj = None
    playwright_obj = None
    
    try:
        # Initialize Playwright
        playwright_obj = sync_playwright().start()
        browser_obj = playwright_obj.chromium.launch(headless=headless)
        page_obj = browser_obj.new_page()
        
        # Set timeout
        page_obj.set_default_timeout(timeout_ms)
        
        logger.info(f"Loading page: {url}")
        
        # Navigate to page
        page_obj.goto(url, wait_until=wait_for_state)
        
        # Wait for network idle or DOM to settle
        page_obj.wait_for_load_state(wait_for_state)
        
        # Scroll to bottom to trigger lazy-loading content
        if scroll_to_bottom:
            logger.debug("Scrolling to bottom of page...")
            page_obj.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # Wait a bit for lazy-loaded content to render
            time.sleep(1)
        
        # Extract content
        html = page_obj.content()
        text = page_obj.inner_text("body")
        title = page_obj.title()
        
        load_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"Page loaded successfully in {load_time_ms:.0f}ms. Size: HTML={len(html)} bytes, Text={len(text)} bytes")
        
        return PageContent(
            html=html,
            text=text,
            url=url,
            title=title,
            load_time_ms=load_time_ms
        )
    
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout loading {url}: {e}")
        if screenshot_on_error and page_obj:
            _save_screenshot(page_obj, url, "timeout")
        raise
    
    except Exception as e:
        logger.error(f"Error loading {url}: {e}", exc_info=True)
        if screenshot_on_error and page_obj:
            _save_screenshot(page_obj, url, "error")
        raise
    
    finally:
        # Cleanup
        if page_obj:
            try:
                page_obj.close()
            except:
                pass
        if browser_obj:
            try:
                browser_obj.close()
            except:
                pass
        if playwright_obj:
            try:
                playwright_obj.stop()
            except:
                pass


def _save_screenshot(page: Page, url: str, reason: str) -> str:
    """
    Save a screenshot for debugging.
    
    Args:
        page: Playwright page object
        url: URL being scraped (for naming)
        reason: Reason for screenshot (e.g., 'error', 'timeout')
    
    Returns:
        Path to saved screenshot
    """
    try:
        screenshot_dir = Path(os.getenv("SCREENSHOT_DIR", "./screenshots"))
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename from URL and reason
        safe_filename = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_filename}_{reason}_{timestamp}.png"
        filepath = screenshot_dir / filename
        
        page.screenshot(path=str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")
        return ""


def extract_meta_tags(page_content: PageContent) -> Dict[str, str]:
    """
    Extract metadata from page (OpenGraph, meta tags, etc.).
    
    Args:
        page_content: PageContent object
    
    Returns:
        Dictionary of meta tags
    """
    import re
    from html.parser import HTMLParser
    
    class MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.meta_tags = {}
        
        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                attrs_dict = dict(attrs)
                if "property" in attrs_dict:
                    self.meta_tags[attrs_dict["property"]] = attrs_dict.get("content", "")
                elif "name" in attrs_dict:
                    self.meta_tags[attrs_dict["name"]] = attrs_dict.get("content", "")
    
    parser = MetaParser()
    try:
        parser.feed(page_content.html[:50000])  # Parse first 50KB
    except:
        pass
    
    return parser.meta_tags
