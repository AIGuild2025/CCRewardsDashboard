"""
Direct HDFC Bank extraction test - bypasses database and uses our validated selectors.
"""

import logging
import yaml
from fetcher.page_loader import load_page
from extractor.rule_based import RuleBasedExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_hdfc_bank():
    """Extract HDFC Bank Pixel Play card details."""
    
    # Load selectors
    with open("config/selectors.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    selectors = config["selectors"].get("HDFC", {}).get("pixel_play_credit_card", {})
    
    print("\n" + "=" * 80)
    print("HDFC BANK - PIXEL PLAY CREDIT CARD EXTRACTION")
    print("=" * 80)
    print(f"\nLoaded Selectors: {selectors}\n")
    
    url = "https://www.hdfc.bank.in/credit-cards/pixel-play-credit-card"
    print(f"Target URL: {url}\n")
    
    try:
        # Load page
        logger.info("Loading page...")
        page = load_page(url, timeout_ms=60000)
        
        if not page:
            print("❌ Failed to load page")
            return False
        
        print(f"✓ Page loaded successfully ({len(page.html)} bytes)\n")
        
        # Extract
        logger.info("Extracting card details...")
        extractor = RuleBasedExtractor(selectors)
        data, confidence = extractor.extract(page.html, url)
        
        print("=" * 80)
        print("EXTRACTION RESULTS")
        print("=" * 80)
        print(f"\nConfidence Score: {confidence:.2f}\n")
        
        if data:
            print("✓ EXTRACTED DATA:\n")
            for field, value in data.items():
                # Limit display for long values
                if len(str(value)) > 200:
                    display_value = str(value)[:200] + "..."
                else:
                    display_value = value
                
                print(f"📌 {field.upper()}")
                print(f"   {display_value}\n")
        else:
            print("❌ No data extracted")
            return False
        
        print("=" * 80)
        
        if confidence >= 0.70:
            print(f"\n✅ EXTRACTION SUCCESSFUL (Confidence: {confidence:.2f})")
            return True
        else:
            print(f"\n⚠️  LOW CONFIDENCE (Confidence: {confidence:.2f})")
            return False
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Extraction Failed: {e}")
        return False

if __name__ == "__main__":
    success = extract_hdfc_bank()
    exit(0 if success else 1)
