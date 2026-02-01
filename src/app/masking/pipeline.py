"""PII masking pipeline with validation."""

import hashlib
import hmac
import re
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from presidio_analyzer import RecognizerResult
from presidio_anonymizer.entities import OperatorConfig

from .engine import get_analyzer, get_anonymizer, get_default_operators


class PIIMaskingPipeline:
    """Pipeline for detecting and masking PII in text data.
    
    Features:
    - Detects multiple PII types (names, cards, emails, phones, Indian IDs)
    - Configurable anonymization strategies per entity type
    - HMAC-based deterministic tokenization for names (consistent per user)
    - Validation pass to detect any leaked PII
    - High-confidence threshold to reduce false positives
    - Smart detection of already-masked data to avoid re-masking
    """
    
    # Patterns to detect already-masked data
    MASKED_PATTERNS = [
        r'[X*]{4,}',  # XXXX or **** (4+ consecutive X's or asterisks)
        r'\[REDACTED\]',  # [REDACTED]
        r'\[MASKED\]',  # [MASKED]
        r'\d{4}[\sX*]{4,}\d{2,4}',  # Patterns like "4532 XXXX XXXX 0366"
        r'[X*]{4}\s[X*]{4}\s[X*]{4}\s[X*]{2,4}\d{2,4}',  # XXXX XXXX XXXX XX95
    ]

    # Heuristic keywords which, when present near a PERSON span, strongly suggest the
    # span is part of a merchant/company string rather than an individual's name.
    #
    # This is intentionally conservative and can be extended as we see more banks.
    _MERCHANT_CONTEXT_RE = re.compile(
        r"\b(?:"
        r"FASHION|STORE|MART|SUPERMARKET|RESTAURANT|CAFE|HOTEL|AIRLINE(?:S)?|TRAVEL(?:S)?|"
        r"PHARMACY|HOSPITAL|CLINIC|PETROL|FUEL|GAS|"
        r"ENTERPRISE(?:S)?|TRADER(?:S)?|INDUSTR(?:Y|IES)|"
        r"BANK|COMPANY|CO\.?|PVT\.?|LTD\.?|LLP"
        r")\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        user_id: Optional[UUID] = None,
        confidence_threshold: float = 0.7,
        operators: Optional[Dict[str, OperatorConfig]] = None,
    ):
        """Initialize the PII masking pipeline.
        
        Args:
            user_id: User ID for deterministic name tokenization
            confidence_threshold: Minimum confidence score for PII detection (0-1)
            operators: Custom anonymization operators (defaults used if None)
        """
        self.analyzer = get_analyzer()
        self.anonymizer = get_anonymizer()
        self.user_id = user_id
        self.confidence_threshold = confidence_threshold
        self.operators = operators or get_default_operators()
    
    def is_already_masked(self, text: str) -> bool:
        """Check if text appears to be already masked.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains masking patterns
        """
        if not text or not text.strip():
            return False
        
        # Check against known masking patterns
        for pattern in self.MASKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
        
    def mask_text(
        self,
        text: str,
        entities_to_mask: Optional[List[str]] = None,
    ) -> str:
        """Mask PII in the given text.
        
        Args:
            text: Input text containing potential PII
            entities_to_mask: List of entity types to mask (None = mask all)
            
        Returns:
            Masked text with PII anonymized
        """
        if not text or not text.strip():
            return text
        
        # Skip if already masked
        if self.is_already_masked(text):
            return text
        
        # Analyze text for PII
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=entities_to_mask,
            score_threshold=self.confidence_threshold,
        )

        operators = self.operators

        # Apply HMAC tokenization for person names if user_id is provided
        if self.user_id:
            results, operators = self._apply_hmac_to_names(text, results)

        # Anonymize detected PII
        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        
        return anonymized.text
    
    def mask_dict(
        self,
        data: Dict[str, any],
        fields_to_mask: Optional[Set[str]] = None,
    ) -> Dict[str, any]:
        """Mask PII in dictionary values.
        
        Args:
            data: Dictionary with potential PII in values
            fields_to_mask: Set of field names to mask (None = mask all string fields)
            
        Returns:
            Dictionary with masked values
        """
        masked_data = {}
        
        for key, value in data.items():
            # Skip if field not in mask list
            if fields_to_mask and key not in fields_to_mask:
                masked_data[key] = value
                continue
            
            # Mask string values
            if isinstance(value, str):
                masked_data[key] = self.mask_text(value)
            # Recursively mask nested dictionaries
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value, fields_to_mask)
            # Mask lists of strings
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_text(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                masked_data[key] = value
        
        return masked_data
    
    def validate_no_leaks(
        self,
        text: str,
        strict: bool = True,
    ) -> tuple[bool, List[str]]:
        """Validate that no PII remains in the text.
        
        This is a safety check to ensure masking was successful.
        
        Args:
            text: Text to validate
            strict: If True, use lower threshold for validation (more sensitive)
            
        Returns:
            Tuple of (is_clean, list_of_detected_entities)
        """
        if not text or not text.strip():
            return True, []
        
        # Use lower threshold for validation to catch edge cases
        threshold = 0.5 if strict else self.confidence_threshold
        
        results = self.analyzer.analyze(
            text=text,
            language="en",
            score_threshold=threshold,
        )
        
        if not results:
            return True, []
        
        # Filter out PERSON and LOCATION entities as they often have false positives
        # (e.g., "Email" detected as PERSON, "[REDACTED]" detected as PERSON)
        # Focus on high-risk PII like emails, phones, credit cards, etc.
        # 
        # NOTE: When adding new recognizers in engine.py, add their entity types here
        # if they represent sensitive data that should be validated.
        sensitive_entity_types = {
            # Identity documents
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "IN_PAN",
            "IN_AADHAAR",
            "IN_MOBILE",
            "US_SSN",
            "US_PASSPORT",
            "IBAN_CODE",
            "IP_ADDRESS",
            # Add more as needed:
            # "US_BANK_NUMBER",
            # "US_DRIVER_LICENSE",
            # "US_ITIN",
            # "MEDICAL_LICENSE",
            # "CRYPTO",
            # "AU_ABN", "AU_ACN", "AU_TFN", "AU_MEDICARE",
            # "ES_NIF",
            # "IT_FISCAL_CODE", "IT_DRIVER_LICENSE", "IT_IDENTITY_CARD", "IT_PASSPORT",
            # "PL_PESEL",
            # "SG_FIN",
        }
        
        # Extract entity types that were detected, filtering for sensitive types
        detected_types = [
            result.entity_type
            for result in results
            if result.entity_type in sensitive_entity_types
        ]
        
        # If no sensitive entities detected, text is clean
        return len(detected_types) == 0, detected_types
    
    def _apply_hmac_to_names(
        self,
        text: str,
        results: List[RecognizerResult],
    ) -> Tuple[List[RecognizerResult], Dict[str, OperatorConfig]]:
        """Apply HMAC-based tokenization to person names.
        
        This creates deterministic tokens that are consistent per user
        but different across users for privacy.
        
        Args:
            text: Original text
            results: Analysis results from Presidio
            
        Returns:
            Tuple of (modified_results, operators_override) for anonymization
        """
        if not self.user_id:
            return results, self.operators
        
        user_key = str(self.user_id).encode()
        operators = dict(self.operators)
        modified_results: List[RecognizerResult] = []
        
        for result in results:
            if result.entity_type == "PERSON":
                # Heuristic: Preserve merchant/company strings even if spaCy mislabels
                # a span as PERSON (common in card statements).
                if self._has_merchant_context(text, result.start, result.end):
                    result.entity_type = "ORGANIZATION"
                    modified_results.append(result)
                    continue

                name = text[result.start:result.end]
                token = hmac.new(
                    key=user_key,
                    msg=name.encode(),
                    digestmod=hashlib.sha256,
                ).hexdigest()[:8]

                # Presidio anonymizer operates per entity type, not per span.
                # To support per-name deterministic tokens, we assign a unique
                # entity type per token and inject a corresponding operator.
                entity_type = f"PERSON_HMAC_{token}"
                result.entity_type = entity_type
                operators[entity_type] = OperatorConfig(
                    "replace",
                    {"new_value": f"[NAME_{token}]"},
                )

            modified_results.append(result)
        
        return modified_results, operators

    @classmethod
    def _has_merchant_context(cls, text: str, start: int, end: int) -> bool:
        # Look around the detected PERSON span for merchant keywords.
        window = 40
        left = max(0, start - window)
        right = min(len(text), end + window)
        return bool(cls._MERCHANT_CONTEXT_RE.search(text[left:right]))
    
    def get_detected_entities(
        self,
        text: str,
    ) -> List[Dict[str, any]]:
        """Get detailed information about detected PII entities.
        
        Useful for debugging and understanding what was detected.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of dictionaries with entity details
        """
        results = self.analyzer.analyze(
            text=text,
            language="en",
            score_threshold=self.confidence_threshold,
        )
        
        entities = []
        for result in results:
            entities.append({
                "type": result.entity_type,
                "text": text[result.start:result.end],
                "start": result.start,
                "end": result.end,
                "score": result.score,
            })
        
        return entities
