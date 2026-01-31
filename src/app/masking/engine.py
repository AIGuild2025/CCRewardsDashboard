"""Presidio analyzer and anonymizer engine setup."""

from functools import lru_cache
from typing import List, Optional

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    # Currently enabled recognizers
    EmailRecognizer,
    PhoneRecognizer,
    IpRecognizer,
    UrlRecognizer,
    DateRecognizer,
    SpacyRecognizer,
    # Available recognizers (uncomment/add as needed)
    # UsSsnRecognizer,
    # UsPassportRecognizer,
    # UsBankRecognizer,
    # UsLicenseRecognizer,
    # UsItinRecognizer,
    # IbanRecognizer,
    # MedicalLicenseRecognizer,
    # CryptoRecognizer,
    # AuAbnRecognizer,
    # AuAcnRecognizer,
    # AuTfnRecognizer,
    # AuMedicareRecognizer,
    # EsNifRecognizer,
    # ItFiscalCodeRecognizer,
    # ItDriverLicenseRecognizer,
    # ItIdentityCardRecognizer,
    # ItPassportRecognizer,
    # PlPeselRecognizer,
    # SgFinRecognizer,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .recognizers import (
    AadhaarRecognizer,
    CreditCardRecognizer,
    IndianMobileRecognizer,
    PANCardRecognizer,
)


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    """Get or create a singleton AnalyzerEngine with custom recognizers.
    
    Returns:
        Configured AnalyzerEngine instance
    """
    # Create NLP engine configuration with spaCy model
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    
    # Create provider and load spaCy model
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    
    # Create registry
    registry = RecognizerRegistry()
    
    # Add custom Indian identity document recognizers
    registry.add_recognizer(PANCardRecognizer())
    registry.add_recognizer(AadhaarRecognizer())
    registry.add_recognizer(IndianMobileRecognizer())
    registry.add_recognizer(CreditCardRecognizer())
    
    # Manually add predefined recognizers we need (avoiding buggy YAML config)
    # This bypasses the default_recognizers.yaml which has a bug in version 2.2.360
    # 
    # TO ADD MORE RECOGNIZERS:
    # 1. Import the recognizer class at the top of this file
    # 2. Add it here with appropriate parameters
    # 3. Update the sensitive_entity_types set in pipeline.py if needed for validation
    # 4. Update the get_default_operators() dict in this file for anonymization strategy
    
    # Email, phone, and network identifiers
    registry.add_recognizer(EmailRecognizer(supported_language="en"))
    registry.add_recognizer(PhoneRecognizer(supported_regions=("US", "IN"), supported_language="en"))
    registry.add_recognizer(IpRecognizer(supported_language="en"))
    registry.add_recognizer(UrlRecognizer(supported_language="en"))
    
    # Date/time information
    registry.add_recognizer(DateRecognizer(supported_language="en"))
    
    # Add more recognizers as needed:
    # registry.add_recognizer(UsSsnRecognizer(supported_language="en"))
    # registry.add_recognizer(IbanRecognizer(supported_language="en"))
    # registry.add_recognizer(UsPassportRecognizer(supported_language="en"))
    # registry.add_recognizer(MedicalLicenseRecognizer(supported_language="en"))
    
    # Add NLP-based person name recognizer
    registry.add_recognizer(SpacyRecognizer(
        supported_language="en",
        supported_entities=["PERSON", "LOCATION", "ORGANIZATION"]
    ))
    
    # Create analyzer
    analyzer = AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"]
    )
    
    return analyzer


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    """Get or create a singleton AnonymizerEngine.
    
    Returns:
        AnonymizerEngine instance
    """
    return AnonymizerEngine()


def get_default_operators() -> dict:
    """Get default anonymization operators for each entity type.
    
    Each entity type can use different anonymization strategies:
    - replace: Replace with fixed text like [REDACTED]
    - mask: Mask characters with * (e.g., keep last 4 digits of credit card)
    - hash: One-way hash for deterministic tokenization
    - keep: Don't anonymize (for non-sensitive data)
    
    NOTE: When adding new recognizers in get_analyzer(), define their
    anonymization strategy here. If not defined, Presidio uses default behavior.
    
    Returns:
        Dictionary mapping entity types to operator configurations
    """
    return {
        # Indian identity documents (partial masking for verification)
        "IN_PAN": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 6,  # Mask first 6 chars, show last 4 (e.g., ABCDE1234F → ******234F)
            "from_end": False
        }),
        "IN_AADHAAR": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 8,  # Mask first 8 digits, show last 4 (e.g., 234567890123 → ********0123)
            "from_end": False
        }),
        "IN_MOBILE": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 10,  # Mask 10 digits, show last 4 (e.g., +91 9876543210 → +91 ******3210)
            "from_end": False
        }),
        
        # Contact information (full redaction for privacy)
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        "PHONE_NUMBER": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 10,  # Show last 4 digits for verification
            "from_end": False
        }),
        
        # Financial information (standard: show last 4, or last 2 for SBI-style)
        "CREDIT_CARD": OperatorConfig("mask", {
            "masking_char": "*",
            "chars_to_mask": 12,  # Last 4 digits (standard): ************0366
            # "chars_to_mask": 14,  # Last 2 digits (SBI-style): **************66
            "from_end": False
        }),
        
        # Personal identifiers
        "PERSON": OperatorConfig("hash", {"hash_type": "sha256"}),
        
        # Location and organization (generally low risk)
        "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
        "ORGANIZATION": OperatorConfig("keep", {}),
        
        # Temporal information (generally OK to keep)
        "DATE_TIME": OperatorConfig("keep", {}),
        
        # Add more as needed when enabling new recognizers:
        # "US_SSN": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        # "US_PASSPORT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        # "IBAN_CODE": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        # "IP_ADDRESS": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        # "MEDICAL_LICENSE": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
    }
