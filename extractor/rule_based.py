"""
Rule-based extraction using XPath and CSS selectors.

Fast path: ~95% of cases should be handled here with high confidence.
If confidence < 70%, fallback to heuristic parsing.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import re
from lxml import html as lxml_html
from lxml.etree import _Element

logger = logging.getLogger(__name__)


class RuleBasedExtractor:
    """
    Fast extraction using XPath and CSS selectors from config.
    """
    
    def __init__(self, selectors: Dict[str, Any]):
        """
        Initialize with selectors from config.
        
        Args:
            selectors: Dict of selectors for card fields
        """
        self.selectors = selectors
        self.confidence = 1.0
    
    def extract(self, html: str, url: str) -> Tuple[Dict[str, Any], float]:
        """
        Extract card data using rule-based selectors.
        
        Args:
            html: Full page HTML
            url: Page URL (for logging)
        
        Returns:
            Tuple of (extracted_data, confidence_score)
            confidence_score: 1.0 = all fields found, decreases for missing fields
        """
        data = {}
        confidence = 1.0
        
        try:
            doc = lxml_html.fromstring(html)
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return {}, 0.0
        
        # Extract each field
        for field_name, selector_config in self.selectors.items():
            try:
                if isinstance(selector_config, str):
                    # Simple CSS selector
                    value = self._extract_by_css(doc, selector_config)
                elif isinstance(selector_config, dict):
                    # Complex selector (xpath, text_pattern, etc.)
                    value = self._extract_by_xpath(doc, selector_config)
                else:
                    value = None
                
                if value:
                    data[field_name] = value
                    logger.debug(f"✓ Extracted {field_name}: {value[:50]}...")
                else:
                    confidence -= 0.15  # Penalty for missing field
                    logger.debug(f"✗ Failed to extract {field_name}")
            
            except Exception as e:
                logger.warning(f"Error extracting {field_name}: {e}")
                confidence -= 0.15
        
        # Final confidence is at least 0 and at most 1
        self.confidence = max(confidence, 0.0)
        
        logger.info(f"Rule-based extraction complete. Confidence: {self.confidence:.2f}")
        return data, self.confidence
    
    def _extract_by_css(self, doc: _Element, selector: str) -> Optional[str]:
        """Extract single value using CSS selector."""
        try:
            elements = doc.cssselect(selector)
            if elements:
                return elements[0].text_content().strip()
        except:
            pass
        return None
    
    def _extract_by_xpath(self, doc: _Element, config: Dict) -> Optional[str]:
        """Extract value using XPath and optional text pattern."""
        xpath = config.get("xpath")
        text_pattern = config.get("text_pattern")
        
        if not xpath:
            return None
        
        try:
            elements = doc.xpath(xpath)
            if not elements:
                return None
            
            # Get text content from first matching element
            element = elements[0]
            if isinstance(element, _Element):
                text = element.text_content().strip()
            else:
                text = str(element).strip()
            
            # Apply regex pattern if provided
            if text_pattern:
                match = re.search(text_pattern, text)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
            
            return text if text else None
        except Exception as e:
            logger.debug(f"XPath extraction failed: {e}")
            return None


def extract_rule_based(
    page_content,
    bank: str,
    selectors: Dict[str, Any]
) -> Tuple[Dict[str, Any], float]:
    """
    Convenience function for rule-based extraction.
    
    Args:
        page_content: PageContent object from fetcher
        bank: Bank name (for logging)
        selectors: Selector config for this bank
    
    Returns:
        Tuple of (extracted_data, confidence_score)
    """
    extractor = RuleBasedExtractor(selectors)
    data, confidence = extractor.extract(page_content.html, page_content.url)
    
    return data, confidence


def extract_text_near(text: str, keyword: str, context_chars: int = 100) -> Optional[str]:
    """
    Extract text near a keyword.
    
    Useful for finding values adjacent to labels like "Annual Fee: $95"
    
    Args:
        text: Full text content
        keyword: Keyword to find
        context_chars: Characters of context to include
    
    Returns:
        Extracted text or None
    """
    idx = text.find(keyword)
    if idx == -1:
        return None
    
    start = max(0, idx + len(keyword))
    end = min(len(text), start + context_chars)
    
    result = text[start:end].strip()
    return result if result else None
