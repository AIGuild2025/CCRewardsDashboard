"""
Debug script to inspect actual HTML content from HDFC Bank page.
"""

import logging
import yaml
from fetcher.page_loader import load_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_hdfc_page():
    """Inspect the actual HTML from HDFC Bank page."""
    
    url = "https://www.hdfc.bank.in/credit-cards/pixel-play-credit-card"
    print(f"Loading: {url}\n")
    
    try:
        page = load_page(url, timeout_ms=60000)
        
        if not page:
            print("Failed to load page")
            return
        
        html = page.html
        
        print("=" * 80)
        print(f"PAGE SIZE: {len(html)} bytes")
        print("=" * 80)
        print("\nACTUAL HTML CONTENT:")
        print("-" * 80)
        print(html)
        print("-" * 80)
        
        # Look for our selectors in the HTML
        print("\n" + "=" * 80)
        print("SELECTOR MATCHING ANALYSIS")
        print("=" * 80)
        
        if "banner-title" in html:
            print("✓ Found: 'banner-title' class")
        else:
            print("✗ NOT found: 'banner-title' class")
        
        if "breakline" in html:
            print("✓ Found: 'breakline' class")
        else:
            print("✗ NOT found: 'breakline' class")
        
        if "card-subtitle" in html:
            print("✓ Found: 'card-subtitle' class")
        else:
            print("✗ NOT found: 'card-subtitle' class")
        
        if "Card Benefits" in html:
            print("✓ Found: 'Card Benefits' text")
        else:
            print("✗ NOT found: 'Card Benefits' text")
        
        if "Wondering if you are eligible" in html:
            print("✓ Found: 'Wondering if you are eligible' text")
        else:
            print("✗ NOT found: 'Wondering if you are eligible' text")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_hdfc_page()
