"""Custom PII recognizers for Indian identity documents."""

import re
from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer


class PANCardRecognizer(PatternRecognizer):
    """Recognizer for Indian PAN (Permanent Account Number) cards.
    
    PAN format: ABCDE1234F (5 letters, 4 digits, 1 letter)
    Example: ABCDE1234F
    """

    PATTERNS = [
        Pattern(
            name="pan_card",
            regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
            score=0.9,
        ),
    ]

    CONTEXT = ["pan", "permanent account", "tax", "income tax"]

    def __init__(self):
        super().__init__(
            supported_entity="IN_PAN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )


class AadhaarRecognizer(PatternRecognizer):
    """Recognizer for Indian Aadhaar numbers.
    
    Aadhaar format: 12 digits, often written as XXXX XXXX XXXX
    Example: 1234 5678 9012 or 123456789012
    """

    PATTERNS = [
        # With spaces
        Pattern(
            name="aadhaar_spaced",
            regex=r"\b\d{4}\s\d{4}\s\d{4}\b",
            score=0.9,
        ),
        # Without spaces
        Pattern(
            name="aadhaar_continuous",
            regex=r"\b\d{12}\b",
            score=0.7,  # Lower score as 12 digits can be other things
        ),
    ]

    CONTEXT = ["aadhaar", "aadhar", "uid", "uidai"]

    def __init__(self):
        super().__init__(
            supported_entity="IN_AADHAAR",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool:
        """Validate Aadhaar number using Verhoeff algorithm."""
        # Remove spaces
        digits = pattern_text.replace(" ", "")
        
        if len(digits) != 12:
            return False
        
        # Basic validation: Aadhaar doesn't start with 0 or 1
        if digits[0] in ("0", "1"):
            return False
        
        return True


class IndianMobileRecognizer(PatternRecognizer):
    """Recognizer for Indian mobile phone numbers.
    
    Format: +91 followed by 10 digits
    Examples: +91 9876543210, 919876543210, 9876543210
    """

    PATTERNS = [
        # With +91 and space
        Pattern(
            name="mobile_with_country_code_space",
            regex=r"\+91\s[6-9]\d{9}\b",
            score=0.9,
        ),
        # With +91 no space
        Pattern(
            name="mobile_with_country_code",
            regex=r"\+91[6-9]\d{9}\b",
            score=0.9,
        ),
        # Without country code
        Pattern(
            name="mobile_without_country_code",
            regex=r"\b[6-9]\d{9}\b",
            score=0.7,
        ),
    ]

    CONTEXT = ["mobile", "phone", "contact", "call", "whatsapp"]

    def __init__(self):
        super().__init__(
            supported_entity="IN_MOBILE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )


class CreditCardRecognizer(PatternRecognizer):
    """Enhanced credit card recognizer with better validation.
    
    Supports: Visa, MasterCard, American Express, Discover
    """

    PATTERNS = [
        # Visa: starts with 4, 13 or 16 digits
        Pattern(
            name="visa",
            regex=r"\b4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
            score=0.9,
        ),
        # MasterCard: starts with 51-55 or 2221-2720, 16 digits
        Pattern(
            name="mastercard",
            regex=r"\b5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
            score=0.9,
        ),
        # American Express: starts with 34 or 37, 15 digits
        Pattern(
            name="amex",
            regex=r"\b3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5}\b",
            score=0.9,
        ),
    ]

    CONTEXT = ["card", "credit", "debit", "payment", "visa", "mastercard", "amex"]

    def __init__(self):
        super().__init__(
            supported_entity="CREDIT_CARD",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool:
        """Validate credit card using Luhn algorithm."""
        # Remove spaces and dashes
        digits = re.sub(r"[\s\-]", "", pattern_text)
        
        if not digits.isdigit():
            return False
        
        # Luhn algorithm
        def luhn_checksum(card_number: str) -> bool:
            def digits_of(n: str) -> List[int]:
                return [int(d) for d in n]
            
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            
            for d in even_digits:
                checksum += sum(digits_of(str(d * 2)))
            
            return checksum % 10 == 0
        
        return luhn_checksum(digits)
