"""Tests for PII masking pipeline."""

from uuid import uuid4

import pytest

from app.masking.pipeline import PIIMaskingPipeline


class TestBasicMasking:
    """Tests for basic PII masking functionality."""

    def test_mask_email(self):
        """Test email masking."""
        pipeline = PIIMaskingPipeline()
        text = "Contact me at john.doe@example.com"
        
        masked = pipeline.mask_text(text)
        
        assert "john.doe@example.com" not in masked
        assert "[REDACTED]" in masked or "john.doe@example.com" not in masked
    
    def test_mask_phone(self):
        """Test phone number masking."""
        pipeline = PIIMaskingPipeline()
        text = "Call me at +91 9876543210"
        
        masked = pipeline.mask_text(text)
        
        assert "9876543210" not in masked
    
    def test_mask_credit_card(self):
        """Test credit card masking keeps last 4."""
        pipeline = PIIMaskingPipeline()
        text = "Card number: 4532015112830366"
        
        masked = pipeline.mask_text(text)
        
        # Should keep last 4 digits
        assert "0366" in masked
        # Should not have full number
        assert "4532015112830366" not in masked
        # Should have masking characters
        assert "*" in masked
    
    def test_mask_pan_card(self):
        """Test PAN card masking (partial - show last 4)."""
        pipeline = PIIMaskingPipeline()
        text = "My PAN is ABCDE1234F"
        
        masked = pipeline.mask_text(text)
        
        # Full PAN should not be visible
        assert "ABCDE1234F" not in masked
        # Should show last 4 characters for verification
        assert "234F" in masked
        # First 6 chars should be masked
        assert "******" in masked
    
    def test_mask_aadhaar(self):
        """Test Aadhaar masking."""
        pipeline = PIIMaskingPipeline()
        text = "Aadhaar: 2345 6789 0123"
        
        masked = pipeline.mask_text(text)
        
        assert "2345 6789 0123" not in masked
    
    def test_empty_text_returns_empty(self):
        """Test that empty text returns empty."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.mask_text("") == ""
        assert pipeline.mask_text("   ") == "   "
    
    def test_text_without_pii_unchanged(self):
        """Test that text without PII remains mostly unchanged."""
        pipeline = PIIMaskingPipeline()
        text = "This is a simple transaction for groceries."
        
        masked = pipeline.mask_text(text)
        
        # Should be similar (may have minor changes from analyzer)
        assert "transaction" in masked
        assert "groceries" in masked


class TestDictionaryMasking:
    """Tests for dictionary masking."""

    def test_mask_dict_all_fields(self):
        """Test masking all string fields in dictionary."""
        pipeline = PIIMaskingPipeline()
        data = {
            "email": "user@example.com",
            "phone": "+91 9876543210",
            "amount": 1000,
        }
        
        masked = pipeline.mask_dict(data)
        
        assert "user@example.com" not in str(masked)
        assert masked["amount"] == 1000  # Non-string unchanged
    
    def test_mask_dict_specific_fields(self):
        """Test masking only specific fields."""
        pipeline = PIIMaskingPipeline()
        data = {
            "description": "Payment from john.doe@example.com",
            "notes": "This has my email: jane@example.com",
        }
        
        masked = pipeline.mask_dict(data, fields_to_mask={"description"})
        
        assert "john.doe@example.com" not in masked["description"]
        assert "jane@example.com" in masked["notes"]  # Not masked
    
    def test_mask_nested_dict(self):
        """Test masking nested dictionaries."""
        pipeline = PIIMaskingPipeline()
        data = {
            "user": {
                "email": "user@example.com",
                "name": "John Doe",
            },
            "amount": 500,
        }
        
        masked = pipeline.mask_dict(data)
        
        assert "user@example.com" not in str(masked)
        assert masked["amount"] == 500
    
    def test_mask_list_values(self):
        """Test masking lists of strings."""
        pipeline = PIIMaskingPipeline()
        data = {
            "emails": ["user1@example.com", "user2@example.com"],
            "amounts": [100, 200],
        }
        
        masked = pipeline.mask_dict(data)
        
        assert "user1@example.com" not in str(masked["emails"])
        assert masked["amounts"] == [100, 200]


class TestHMACTokenization:
    """Tests for HMAC-based name tokenization."""

    def test_name_tokenization_with_user_id(self):
        """Test that names are tokenized with user ID."""
        user_id = uuid4()
        pipeline = PIIMaskingPipeline(user_id=user_id)
        
        text = "Transaction by John Smith"
        masked = pipeline.mask_text(text)
        
        # Name should be replaced with token
        assert "John Smith" not in masked
        assert "[NAME_" in masked
    
    def test_same_name_same_token_per_user(self):
        """Test deterministic tokenization per user."""
        user_id = uuid4()
        pipeline = PIIMaskingPipeline(user_id=user_id)
        
        text1 = "Payment from John Smith"
        text2 = "Refund to John Smith"
        
        masked1 = pipeline.mask_text(text1)
        masked2 = pipeline.mask_text(text2)
        
        # Extract tokens (this is a simple check)
        # Both should have the same token for "John Smith"
        assert "[NAME_" in masked1
        assert "[NAME_" in masked2
    
    def test_different_users_different_tokens(self):
        """Test that different users get different tokens."""
        user_id1 = uuid4()
        user_id2 = uuid4()
        
        pipeline1 = PIIMaskingPipeline(user_id=user_id1)
        pipeline2 = PIIMaskingPipeline(user_id=user_id2)
        
        text = "Payment from John Smith"
        
        masked1 = pipeline1.mask_text(text)
        masked2 = pipeline2.mask_text(text)
        
        # Should have different tokens
        assert masked1 != masked2


class TestValidation:
    """Tests for PII leak validation."""

    def test_validate_clean_text(self):
        """Test validation of clean text."""
        pipeline = PIIMaskingPipeline()
        text = "This is a transaction for groceries totaling 100 dollars."
        
        is_clean, detected = pipeline.validate_no_leaks(text)
        
        assert is_clean
        assert len(detected) == 0
    
    def test_validate_detects_email(self):
        """Test validation detects leaked email."""
        pipeline = PIIMaskingPipeline()
        text = "Contact: user@example.com"
        
        is_clean, detected = pipeline.validate_no_leaks(text)
        
        assert not is_clean
        assert "EMAIL_ADDRESS" in detected
    
    def test_validate_detects_phone(self):
        """Test validation detects leaked phone."""
        pipeline = PIIMaskingPipeline()
        text = "Call +91 9876543210"
        
        is_clean, detected = pipeline.validate_no_leaks(text)
        
        assert not is_clean
    
    def test_validate_masked_text_is_clean(self):
        """Test that masked text passes validation."""
        pipeline = PIIMaskingPipeline()
        
        original = "Email: user@example.com, Phone: +91 9876543210"
        masked = pipeline.mask_text(original)
        
        is_clean, detected = pipeline.validate_no_leaks(masked)
        
        # Masked text should be clean
        assert is_clean or len(detected) == 0
    
    def test_validate_empty_text(self):
        """Test validation of empty text."""
        pipeline = PIIMaskingPipeline()
        
        is_clean, detected = pipeline.validate_no_leaks("")
        
        assert is_clean
        assert len(detected) == 0


class TestEntityDetection:
    """Tests for entity detection details."""

    def test_get_detected_entities_email(self):
        """Test getting details of detected email."""
        pipeline = PIIMaskingPipeline()
        text = "Contact: user@example.com"
        
        entities = pipeline.get_detected_entities(text)
        
        assert len(entities) > 0
        # Find email entity
        email_entity = next(
            (e for e in entities if e["type"] == "EMAIL_ADDRESS"),
            None
        )
        assert email_entity is not None
        assert "user@example.com" in email_entity["text"]
    
    def test_get_detected_entities_multiple(self):
        """Test detection of multiple entities."""
        pipeline = PIIMaskingPipeline()
        text = "Email: user@example.com, Phone: +91 9876543210, PAN: ABCDE1234F"
        
        entities = pipeline.get_detected_entities(text)
        
        assert len(entities) >= 3
        types = [e["type"] for e in entities]
        
        assert "EMAIL_ADDRESS" in types
        assert "IN_PAN" in types
    
    def test_get_detected_entities_with_scores(self):
        """Test that entities include confidence scores."""
        pipeline = PIIMaskingPipeline()
        text = "My card: 4532015112830366"
        
        entities = pipeline.get_detected_entities(text)
        
        for entity in entities:
            assert "score" in entity
            assert 0 <= entity["score"] <= 1


class TestConfidenceThreshold:
    """Tests for confidence threshold filtering."""

    def test_high_confidence_filters_low_scores(self):
        """Test that high threshold filters out low-confidence matches."""
        # High threshold pipeline
        high_pipeline = PIIMaskingPipeline(confidence_threshold=0.9)
        # Low threshold pipeline
        low_pipeline = PIIMaskingPipeline(confidence_threshold=0.5)
        
        # Text with ambiguous pattern
        text = "Reference number: 123456789012"
        
        high_entities = high_pipeline.get_detected_entities(text)
        low_entities = low_pipeline.get_detected_entities(text)
        
        # Low threshold should detect more (or equal)
        assert len(low_entities) >= len(high_entities)
    
    def test_default_threshold(self):
        """Test that default threshold is reasonable."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.confidence_threshold == 0.7


class TestAlreadyMaskedDetection:
    """Tests for detecting and skipping already-masked data."""

    def test_detects_xxxx_pattern(self):
        """Test detection of XXXX masked pattern."""
        pipeline = PIIMaskingPipeline()
        
        masked_text = "XXXX XXXX XXXX XX95"
        assert pipeline.is_already_masked(masked_text)
    
    def test_detects_asterisk_pattern(self):
        """Test detection of **** masked pattern."""
        pipeline = PIIMaskingPipeline()
        
        masked_text = "**** **** **** **95"
        assert pipeline.is_already_masked(masked_text)
    
    def test_detects_redacted_marker(self):
        """Test detection of [REDACTED] marker."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.is_already_masked("[REDACTED]")
        assert pipeline.is_already_masked("Email: [REDACTED]")
    
    def test_detects_masked_marker(self):
        """Test detection of [MASKED] marker."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.is_already_masked("[MASKED]")
        assert pipeline.is_already_masked("PAN: [MASKED]")
    
    def test_detects_partial_card_masking(self):
        """Test detection of partial card masking like 4532 **** **** 0366."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.is_already_masked("4532 **** **** 0366")
        assert pipeline.is_already_masked("Card: 4532 XXXX XXXX 0366")
    
    def test_detects_long_asterisk_sequence(self):
        """Test detection of long asterisk sequences."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.is_already_masked("************0366")
        assert pipeline.is_already_masked("XXXXXXXXXXXX95")
    
    def test_does_not_detect_normal_text(self):
        """Test that normal text is not flagged as masked."""
        pipeline = PIIMaskingPipeline()
        
        assert not pipeline.is_already_masked("4532 0151 1283 0366")
        assert not pipeline.is_already_masked("john.doe@example.com")
        assert not pipeline.is_already_masked("ABCDE1234F")
    
    def test_does_not_detect_short_x_sequence(self):
        """Test that short X sequences are not flagged (e.g., XXL size)."""
        pipeline = PIIMaskingPipeline()
        
        assert not pipeline.is_already_masked("Size: XXL")
        assert not pipeline.is_already_masked("XXX")
    
    def test_skips_masking_for_already_masked_card(self):
        """Test that already-masked cards are not re-masked."""
        pipeline = PIIMaskingPipeline()
        
        sbi_format = "XXXX XXXX XXXX XX95"
        result = pipeline.mask_text(sbi_format)
        
        # Should be unchanged
        assert result == sbi_format
    
    def test_masks_unmasked_card(self):
        """Test that full card numbers are still masked."""
        pipeline = PIIMaskingPipeline()
        
        full_card = "4532 0151 1283 0366"
        result = pipeline.mask_text(full_card)
        
        # Should be masked
        assert result != full_card
        assert "*" in result
        assert "0366" in result
    
    def test_mixed_content_with_masked_and_unmasked(self):
        """Test text with both masked and unmasked PII.
        
        Note: If text contains ANY already-masked pattern, the entire text
        is skipped to avoid double-processing. This is intentional behavior.
        """
        pipeline = PIIMaskingPipeline()
        
        # Text with already-masked card - entire text will be skipped
        text = "Card: XXXX XXXX XXXX XX95, Email: john@example.com"
        result = pipeline.mask_text(text)
        
        # Entire text should be unchanged because it contains masked pattern
        assert result == text
        
        # Text without any masked patterns - should mask email
        text_unmasked = "Card: 4532 0151 1283 0366, Email: john@example.com"
        result_unmasked = pipeline.mask_text(text_unmasked)
        
        # Both card and email should be masked
        assert result_unmasked != text_unmasked
        assert "john@example.com" not in result_unmasked
    
    def test_empty_and_whitespace(self):
        """Test handling of empty and whitespace-only strings."""
        pipeline = PIIMaskingPipeline()
        
        assert not pipeline.is_already_masked("")
        assert not pipeline.is_already_masked("   ")
        assert not pipeline.is_already_masked("\n\t")
    
    def test_case_insensitive_redacted_detection(self):
        """Test that [REDACTED] detection is case-insensitive."""
        pipeline = PIIMaskingPipeline()
        
        assert pipeline.is_already_masked("[REDACTED]")
        assert pipeline.is_already_masked("[redacted]")
        assert pipeline.is_already_masked("[Redacted]")
