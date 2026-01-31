"""Tests for Presidio engine setup."""

import pytest

from app.masking.engine import get_analyzer, get_anonymizer, get_default_operators


class TestAnalyzerEngine:
    """Tests for analyzer engine."""

    def test_analyzer_singleton(self):
        """Test that analyzer returns same instance."""
        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()
        
        assert analyzer1 is analyzer2
    
    def test_analyzer_has_custom_recognizers(self):
        """Test that custom recognizers are loaded."""
        analyzer = get_analyzer()
        
        # Get all supported entities
        supported_entities = set()
        for recognizer in analyzer.registry.recognizers:
            supported_entities.update(recognizer.supported_entities)
        
        # Check for our custom entities
        assert "IN_PAN" in supported_entities
        assert "IN_AADHAAR" in supported_entities
        assert "IN_MOBILE" in supported_entities
        assert "CREDIT_CARD" in supported_entities
    
    def test_analyzer_has_default_recognizers(self):
        """Test that default recognizers are loaded."""
        analyzer = get_analyzer()
        
        supported_entities = set()
        for recognizer in analyzer.registry.recognizers:
            supported_entities.update(recognizer.supported_entities)
        
        # Check for standard entities
        assert "EMAIL_ADDRESS" in supported_entities
        assert "PHONE_NUMBER" in supported_entities


class TestAnonymizerEngine:
    """Tests for anonymizer engine."""

    def test_anonymizer_singleton(self):
        """Test that anonymizer returns same instance."""
        anon1 = get_anonymizer()
        anon2 = get_anonymizer()
        
        assert anon1 is anon2


class TestDefaultOperators:
    """Tests for default anonymization operators."""

    def test_operators_cover_all_entities(self):
        """Test that operators are defined for all entity types."""
        operators = get_default_operators()
        
        expected_entities = [
            "IN_PAN",
            "IN_AADHAAR",
            "IN_MOBILE",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "PERSON",
            "LOCATION",
            "DATE_TIME",
        ]
        
        for entity in expected_entities:
            assert entity in operators, f"Missing operator for {entity}"
    
    def test_sensitive_entities_redacted(self):
        """Test that sensitive entities use masking or redaction."""
        operators = get_default_operators()
        
        # These use partial masking (show last 4)
        masked_entities = [
            "IN_PAN",
            "IN_AADHAAR",
            "IN_MOBILE",
            "PHONE_NUMBER",
        ]
        
        # These use full redaction
        redacted_entities = [
            "EMAIL_ADDRESS",
        ]
        
        for entity in masked_entities:
            assert operators[entity].operator_name == "mask"
        
        for entity in redacted_entities:
            assert operators[entity].operator_name == "replace"
    
    def test_credit_card_masked(self):
        """Test that credit cards use masking."""
        operators = get_default_operators()
        
        assert operators["CREDIT_CARD"].operator_name == "mask"
        assert operators["CREDIT_CARD"].params["masking_char"] == "*"
        assert operators["CREDIT_CARD"].params["chars_to_mask"] == 12
    
    def test_person_name_hashed(self):
        """Test that person names use hashing."""
        operators = get_default_operators()
        
        assert operators["PERSON"].operator_name == "hash"
        assert operators["PERSON"].params["hash_type"] == "sha256"
