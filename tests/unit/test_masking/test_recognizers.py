"""Tests for custom PII recognizers."""

import pytest

from app.masking.recognizers import (
    AadhaarRecognizer,
    CreditCardRecognizer,
    IndianMobileRecognizer,
    PANCardRecognizer,
)


class TestPANCardRecognizer:
    """Tests for PAN card recognizer."""

    def test_valid_pan_detected(self):
        """Test that valid PAN numbers are detected."""
        recognizer = PANCardRecognizer()
        text = "My PAN is ABCDE1234F"
        
        # Create a simple test - just check if pattern matches
        import re
        pattern = recognizer.patterns[0].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
        assert matches[0] == "ABCDE1234F"
    
    def test_invalid_pan_not_detected(self):
        """Test that invalid PAN formats are not detected."""
        recognizer = PANCardRecognizer()
        
        invalid_pans = [
            "ABC1234F",  # Too short
            "ABCDE12345F",  # Too long
            "abcde1234f",  # Lowercase
            "ABCD11234F",  # Wrong format
        ]
        
        pattern = recognizer.patterns[0].regex
        for invalid in invalid_pans:
            import re
            matches = re.findall(pattern, f"PAN: {invalid}")
            assert len(matches) == 0, f"Should not match: {invalid}"
    
    def test_multiple_pans_detected(self):
        """Test detection of multiple PAN numbers in text."""
        recognizer = PANCardRecognizer()
        text = "PANs: ABCDE1234F and XYZAB5678C"
        
        import re
        pattern = recognizer.patterns[0].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 2


class TestAadhaarRecognizer:
    """Tests for Aadhaar number recognizer."""

    def test_aadhaar_with_spaces(self):
        """Test detection of Aadhaar with spaces."""
        recognizer = AadhaarRecognizer()
        text = "Aadhaar: 2345 6789 0123"
        
        import re
        pattern = recognizer.patterns[0].regex  # Spaced pattern
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_aadhaar_without_spaces(self):
        """Test detection of Aadhaar without spaces."""
        recognizer = AadhaarRecognizer()
        text = "Aadhaar: 234567890123"
        
        import re
        pattern = recognizer.patterns[1].regex  # Continuous pattern
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_aadhaar_validation_rejects_starting_with_zero(self):
        """Test that Aadhaar starting with 0 is rejected."""
        recognizer = AadhaarRecognizer()
        
        assert not recognizer.validate_result("012345678901")
    
    def test_aadhaar_validation_rejects_starting_with_one(self):
        """Test that Aadhaar starting with 1 is rejected."""
        recognizer = AadhaarRecognizer()
        
        assert not recognizer.validate_result("112345678901")
    
    def test_aadhaar_validation_accepts_valid(self):
        """Test that valid Aadhaar is accepted."""
        recognizer = AadhaarRecognizer()
        
        assert recognizer.validate_result("234567890123")
        assert recognizer.validate_result("2345 6789 0123")


class TestIndianMobileRecognizer:
    """Tests for Indian mobile number recognizer."""

    def test_mobile_with_country_code_space(self):
        """Test detection with +91 and space."""
        recognizer = IndianMobileRecognizer()
        text = "Call me at +91 9876543210"
        
        import re
        pattern = recognizer.patterns[0].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_mobile_with_country_code_no_space(self):
        """Test detection with +91 without space."""
        recognizer = IndianMobileRecognizer()
        text = "WhatsApp: +919876543210"
        
        import re
        pattern = recognizer.patterns[1].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_mobile_without_country_code(self):
        """Test detection without country code."""
        recognizer = IndianMobileRecognizer()
        text = "Mobile: 9876543210"
        
        import re
        pattern = recognizer.patterns[2].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_invalid_mobile_not_detected(self):
        """Test that invalid mobile numbers are not detected."""
        recognizer = IndianMobileRecognizer()
        
        # Indian mobiles must start with 6-9
        invalid_numbers = [
            "1234567890",  # Starts with 1
            "5987654321",  # Starts with 5
        ]
        
        for pattern in recognizer.patterns:
            import re
            for invalid in invalid_numbers:
                matches = re.findall(pattern.regex, f"Phone: {invalid}")
                assert len(matches) == 0


class TestCreditCardRecognizer:
    """Tests for credit card recognizer."""

    def test_visa_card_detected(self):
        """Test Visa card detection."""
        recognizer = CreditCardRecognizer()
        text = "Card: 4532015112830366"
        
        import re
        pattern = recognizer.patterns[0].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_mastercard_detected(self):
        """Test MasterCard detection."""
        recognizer = CreditCardRecognizer()
        text = "Card: 5425233430109903"
        
        import re
        pattern = recognizer.patterns[1].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_amex_detected(self):
        """Test American Express detection."""
        recognizer = CreditCardRecognizer()
        text = "Card: 374245455400126"
        
        import re
        pattern = recognizer.patterns[2].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_card_with_spaces(self):
        """Test card number with spaces."""
        recognizer = CreditCardRecognizer()
        text = "Card: 4532 0151 1283 0366"
        
        import re
        pattern = recognizer.patterns[0].regex
        matches = re.findall(pattern, text)
        
        assert len(matches) == 1
    
    def test_luhn_validation_valid_card(self):
        """Test Luhn algorithm with valid card."""
        recognizer = CreditCardRecognizer()
        
        # Valid test cards from payment processors
        assert recognizer.validate_result("4532015112830366")  # Visa
        assert recognizer.validate_result("5425233430109903")  # MasterCard
        assert recognizer.validate_result("374245455400126")   # Amex
    
    def test_luhn_validation_invalid_card(self):
        """Test Luhn algorithm with invalid card."""
        recognizer = CreditCardRecognizer()
        
        # Invalid cards (wrong check digit)
        assert not recognizer.validate_result("4532015112830367")
        assert not recognizer.validate_result("5425233430109904")
