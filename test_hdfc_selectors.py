"""
Quick test script to validate HDFC Bank selectors.
Tests if the new selectors are extracting data correctly.
"""

import logging
import yaml
from fetcher.page_loader import load_page
from extractor.rule_based import RuleBasedExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_hdfc_selectors():
    """Test HDFC Bank selectors on the Pixel Play card page."""
    
    # Load selectors
    with open("config/selectors.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    selectors = config["selectors"].get("HDFC Bank", {}).get("premium_rewards", {})
    
    print("=" * 80)
    print("HDFC Bank Selector Test")
    print("=" * 80)
    print(f"\nLoaded selectors: {selectors}\n")
    
    # Test URL
    url = "https://www.hdfc.bank.in/credit-cards/pixel-play-credit-card"
    print(f"Testing URL: {url}\n")
    
    try:
        # Load page
        logger.info("Loading page...")
        page = load_page(url, timeout_ms=60000)
        
        if not page:
            print("❌ Failed to load page")
            return False
        
        html = page.html
        print(f"✓ Page loaded successfully ({len(html)} bytes)\n")
        
        # Extract using rule-based extractor
        logger.info("Extracting data...")
        extractor = RuleBasedExtractor(selectors)
        data, confidence = extractor.extract(html, url)
        
        print("=" * 80)
        print("EXTRACTION RESULTS")
        print("=" * 80)
        print(f"\nConfidence Score: {confidence:.2f}\n")
        
        print("Extracted Fields:")
        print("-" * 80)
        if data:
            for field, value in data.items():
                # Truncate long values for display
                display_value = value[:100] + "..." if len(str(value)) > 100 else value
                print(f"  ✓ {field:20s}: {display_value}")
        else:
            print("  ❌ No data extracted")
        
        print("\n" + "=" * 80)
        
        # Check which fields were extracted
        expected_fields = ["card_name", "benefits", "eligibility"]
        missing_fields = [f for f in expected_fields if f not in data]
        
        if missing_fields:
            print(f"\n⚠️  Missing fields: {missing_fields}")
            print("\nTroubleshooting tips:")
            print("1. Check if the selectors match the current HTML structure")
            print("2. Use browser DevTools to inspect the elements")
            print("3. Update selectors in config/selectors.yaml if HTML changed")
            print("4. Test individual XPath expressions in the browser console")
            return False
        else:
            print(f"\n✓ All expected fields extracted successfully!")
            return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_hdfc_selectors()
    exit(0 if success else 1)
