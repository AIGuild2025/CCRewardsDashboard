"""
Debug script to test each selector individually.
"""

from lxml import html as lxml_html

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
        
        <!-- Card Benefits Section -->
        <span class="breakline" data-font-size="48" 
              data-line-height="57.599999999999994" data-letter-spacing="normal">
            Card Benefits &amp; Features
        </span>
        
        <!-- Eligibility Section -->
        <span class="card-subtitle aos-init aos-animate" data-aos="fade-up" 
              data-aos-duration="700" data-aos-delay="200" 
              data-labeltext="Wondering if you are eligible?" data-font-size="48" 
              data-line-height="57.599999999999994" data-letter-spacing="normal">
            Wondering if you are eligible?
        </span>
    </div>
</body>
</html>
'''

def debug_selectors():
    """Debug each selector."""
    doc = lxml_html.fromstring(MOCK_HTML)
    
    print("\n" + "=" * 80)
    print("SELECTOR DEBUG")
    print("=" * 80 + "\n")
    
    # Test 1: card_name CSS selector
    print("1. CSS Selector: span.banner-title")
    print("-" * 80)
    try:
        elements = doc.cssselect('span.banner-title')
        if elements:
            text = elements[0].text_content().strip()
            print(f"✓ Found: {text}\n")
        else:
            print(f"✗ No elements found\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
    
    # Test 2: benefits XPath (current)
    print("2. XPath: //span[@class='breakline' and contains(text(), 'Card Benefits')]")
    print("-" * 80)
    xpath = "//span[@class='breakline' and contains(text(), 'Card Benefits')]"
    try:
        elements = doc.xpath(xpath)
        if elements:
            text = elements[0].text_content().strip()
            print(f"✓ Found: {text}\n")
        else:
            print(f"✗ No elements found\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
    
    # Test 3: eligibility XPath (current)
    print("3. XPath: //span[@class='card-subtitle' and contains(text(), 'Wondering if you are eligible')]")
    print("-" * 80)
    xpath = "//span[@class='card-subtitle' and contains(text(), 'Wondering if you are eligible')]"
    try:
        elements = doc.xpath(xpath)
        if elements:
            text = elements[0].text_content().strip()
            print(f"✓ Found: {text}\n")
        else:
            print(f"✗ No elements found - checking partial matches...\n")
            
            # Check if element exists at all
            xpath_simple = "//span[@class='card-subtitle']"
            elements = doc.xpath(xpath_simple)
            if elements:
                text = elements[0].text_content().strip()
                print(f"  Element exists with different text content:")
                print(f"  Actual text: {text}")
                print(f"  Looking for substring: 'Wondering if you are eligible'\n")
            else:
                print("  Element with class 'card-subtitle' not found at all\n")
                
    except Exception as e:
        print(f"✗ Error: {e}\n")
    
    # Alternative eligibility selectors
    print("4. Alternative: //span[contains(@class, 'card-subtitle')]")
    print("-" * 80)
    xpath = "//span[contains(@class, 'card-subtitle')]"
    try:
        elements = doc.xpath(xpath)
        if elements:
            text = elements[0].text_content().strip()
            print(f"✓ Found: {text}\n")
        else:
            print(f"✗ No elements found\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
    
    print("=" * 80)
    print("RECOMMENDED FIXES")
    print("=" * 80)
    print("""
The issue is that the XPath predicates are too strict. The text content includes 
HTML entities like '&amp;' which don't match literally in XPath text matching.

RECOMMENDATIONS:

1. card_name - WORKS as CSS selector:
   card_name: "span.banner-title"
   ✓ Already correct in config

2. benefits - WORKS as is:
   xpath: "//span[@class='breakline' and contains(text(), 'Card Benefits')]"
   ✓ Already works

3. eligibility - NEEDS FIX:
   Change from:
   xpath: "//span[@class='card-subtitle' and contains(text(), 'Wondering if you are eligible')]"
   
   To (more flexible):
   xpath: "//span[contains(@class, 'card-subtitle')]"
   
   This removes the text matching which can be brittle and just matches the class.
""")

if __name__ == "__main__":
    debug_selectors()
