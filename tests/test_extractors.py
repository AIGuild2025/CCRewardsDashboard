"""
Unit tests for extractors.
"""

import pytest
from extractor.rule_based import RuleBasedExtractor, extract_text_near
from extractor.heuristic import HeuristicExtractor
from normalizer.card_schema import Normalizer


class TestRuleBasedExtractor:
    """Test rule-based extraction."""
    
    def test_extract_empty_selectors(self):
        """Test with no selectors."""
        extractor = RuleBasedExtractor({})
        data, confidence = extractor.extract("<html><body>Test</body></html>", "http://test.com")
        
        assert confidence == 1.0  # No fields to extract = no penalty
        assert data == {}
    
    def test_extract_with_simple_selector(self):
        """Test CSS selector extraction."""
        html = '<html><body><h1>Chase Sapphire</h1></body></html>'
        selectors = {"card_name": "h1"}
        
        extractor = RuleBasedExtractor(selectors)
        data, confidence = extractor.extract(html, "http://test.com")
        
        assert "card_name" in data
        assert data["card_name"] == "Chase Sapphire"
        assert confidence >= 0.85
    
    def test_extract_text_near(self):
        """Test text extraction near keyword."""
        text = "Annual Fee: $95 per year"
        result = extract_text_near(text, "Annual Fee:", context_chars=20)
        
        assert result is not None
        assert "$95" in result


class TestHeuristicExtractor:
    """Test heuristic extraction."""
    
    def test_extract_with_sections(self):
        """Test section-based extraction."""
        text = """
        CHASE SAPPHIRE PREFERRED
        
        ANNUAL FEE
        $95 annual fee
        
        BENEFITS
        3x points on travel
        Free luggage insurance
        """
        
        extractor = HeuristicExtractor()
        data, confidence = extractor.extract(text, "http://test.com")
        
        assert data.get("card_name") is not None
        assert confidence > 0.3  # Should find some data


class TestNormalizer:
    """Test schema normalization."""
    
    def test_normalize_with_valid_data(self):
        """Test normalization of valid extracted data."""
        raw_data = {
            "card_name": "Chase Sapphire Preferred",
            "annual_fee": "$95",
            "benefits": ["3x travel", "2x dining"]
        }
        
        normalizer = Normalizer("Chase")
        normalized = normalizer.normalize(raw_data, "http://test.com", 0.9)
        
        assert normalized.card_name == "Chase Sapphire Preferred"
        assert normalized.bank_name == "Chase"
        assert normalized.annual_fee == 95  # Converted to float
        assert normalized.benefits is not None
    
    def test_normalize_extracts_annual_fee(self):
        """Test annual fee extraction from various formats."""
        normalizer = Normalizer("Test")
        
        # Test string with dollar sign
        data = normalizer._extract_annual_fee({"fees": {"annual": "$95"}})
        assert data == 95
        
        # Test numeric fee
        data = normalizer._extract_annual_fee({"annual_fee": 150.0})
        assert data == 150.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
