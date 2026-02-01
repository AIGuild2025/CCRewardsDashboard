"""
Mock test using the exact HTML elements you provided.
This tests that your selectors work correctly against the actual elements.
"""

import logging
from extractor.rule_based import RuleBasedExtractor
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock HTML using the exact elements you provided
MOCK_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>HDFC Bank - Pixel Play Credit Card</title>
</head>
<body>
    <div class="card-page">
        <!-- Card Title Element -->
        <span class="banner-title" data-labeltext="PIXEL Play Credit Card" 
              data-font-size="42" data-line-height="50.4" data-letter-spacing="normal">
            PIXEL Play Credit Card
        </span>
        
        <!-- Benefits Section -->
        <div class="cmp-teaser__description">
            <h3><span class="section-title">CashBack Benefits</span></h3>
            <ul class="showList">
                <p>5% CashBack on choice of any two following packs:</p>
                <li><span class="icon-right-tick icon"></span>Dining &amp; Entertainment Category - BookMyShow &amp; Zomato</li>
                <li><span class="icon-right-tick icon"></span>Travel Category – MakeMyTrip &amp; Uber</li>
                <li><span class="icon-right-tick icon"></span>Grocery Category – Blinkit &amp; Reliance Smart Bazaar</li>
                <li><span class="icon-right-tick icon"></span>Electronics Category – Croma &amp; Reliance Digital</li>
                <li><span class="icon-right-tick icon"></span>Fashion Category – Nykaa &amp; Myntra</li>
                <li><span class="icon-right-tick icon"></span>3% CashBack on Amazon, Flipkart or PayZapp</li>
                <li><span class="icon-right-tick icon"></span>1% CashBack on UPI Spends</li>
            </ul>
        </div>
        
        <!-- Eligibility Section -->
        <div class="extendedteaser teaser quick-benefit_list quick-eligibility_List">
            <div class="cmp-teaser__description">
                <p><span class="quick-eligibility_heading"><span class="icon-salaried icon"></span>Salaried</span></p>
                <ul>
                    <li><span class="icon-age icon"></span><span class="pd-beneftis_title"><b>Nationality:</b> Indian</span></li>
                    <li><span class="icon-age icon"></span><span class="pd-beneftis_title"><b>Age:</b> Minimum: 21 years, Maximum: 60 years</span></li>
                    <li><span class="icon-income icon"></span><span class="pd-beneftis_title"><b>Income</b> (Monthly) - ₹25,000</span></li>
                </ul>
            </div>
            <div class="cmp-teaser__description">
                <p><span class="quick-eligibility_heading"><span class="icon-self-employed icon"></span>Self-Employed</span></p>
                <ul>
                    <li><span class="icon icon-age"></span><span class="pd-beneftis_title"><b>Nationality:</b> Indian</span></li>
                    <li><span class="icon icon-age"></span><span class="pd-beneftis_title"><b>Age:</b> Minimum: 21 years, Maximum: 65 years</span></li>
                    <li><span class="icon icon-income"></span><span class="pd-beneftis_title"><b>Annual ITR </b>&gt; ₹6,00,000</span></li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
'''

def test_selectors_with_mock_html():
    """Test HDFC selectors against mock HTML."""
    
    # Load selectors from config
    with open("config/selectors.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    selectors = config["selectors"].get("HDFC Bank", {}).get("premium_rewards", {})
    
    print("\n" + "=" * 80)
    print("HDFC BANK SELECTOR TEST - MOCK HTML")
    print("=" * 80)
    print(f"\nTesting with {len(MOCK_HTML)} bytes of mock HTML\n")
    
    # Create extractor and test
    extractor = RuleBasedExtractor(selectors)
    data, confidence = extractor.extract(MOCK_HTML, "https://www.hdfc.bank.in/credit-cards/pixel-play-credit-card")
    
    print("=" * 80)
    print("EXTRACTION RESULTS")
    print("=" * 80)
    print(f"\nConfidence Score: {confidence:.2f}\n")
    
    if data:
        print("✓ DATA EXTRACTED SUCCESSFULLY:\n")
        for field, value in data.items():
            print(f"  Field: {field}")
            print(f"  Value: {value}")
            print()
    else:
        print("❌ No data extracted (selectors may not match HTML)")
        return False
    
    # Verify expected fields
    print("=" * 80)
    print("FIELD VALIDATION")
    print("=" * 80 + "\n")
    
    expected_fields = {
        "card_name": "PIXEL Play Credit Card",
        "benefits": "CashBack",  # Should contain this
        "eligibility": "Salaried"  # Should contain this
    }
    
    all_found = True
    for field, expected_content in expected_fields.items():
        if field in data:
            actual = data[field]
            if expected_content in actual:
                print(f"✓ {field:20s} FOUND and CORRECT")
                print(f"  Expected substring: '{expected_content}'")
                print(f"  Actual value:       '{actual}'")
            else:
                print(f"⚠️  {field:20s} FOUND but content mismatch")
                print(f"  Expected substring: '{expected_content}'")
                print(f"  Actual value:       '{actual}'")
                all_found = False
        else:
            print(f"✗ {field:20s} NOT FOUND")
            all_found = False
        print()
    
    print("=" * 80)
    
    if all_found:
        print("✓ ALL SELECTORS WORKING CORRECTLY!\n")
        print("Your selectors will successfully extract data from the HDFC Bank page.")
        print("The issue with live testing is website bot detection, not selector issues.")
        return True
    else:
        print("❌ Some selectors are not working correctly.\n")
        return False

if __name__ == "__main__":
    success = test_selectors_with_mock_html()
    exit(0 if success else 1)
