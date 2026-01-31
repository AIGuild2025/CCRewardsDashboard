"""
Tests for schema validation.
"""

import pytest
from normalizer.card_schema import CardNormalized, CardFees, Normalizer
from diff_engine import ChangeComparator, CardDiff


class TestCardSchema:
    """Test card schema validation."""
    
    def test_valid_card_schema(self):
        """Test creating valid card."""
        card = CardNormalized(
            card_name="Chase Sapphire Preferred",
            bank_name="Chase",
            annual_fee=95,
            base_earning_rate=1.0,
            category_bonuses={"travel": 3.0, "dining": 3.0}
        )
        
        assert card.card_name == "Chase Sapphire Preferred"
        assert card.annual_fee == 95
        assert card.meta is not None
    
    def test_card_schema_json(self):
        """Test card serialization to JSON."""
        card = CardNormalized(
            card_name="AmEx Platinum",
            bank_name="AmEx",
            annual_fee=695
        )
        
        card_dict = card.dict()
        assert card_dict["card_name"] == "AmEx Platinum"
        assert card_dict["annual_fee"] == 695


class TestDiffEngine:
    """Test change detection."""
    
    def test_first_scrape_no_old_data(self):
        """Test diff when no previous data exists."""
        new_data = {
            "card_name": "New Card",
            "annual_fee": 100,
            "bank_name": "Test Bank"
        }
        
        diff = ChangeComparator.compare(None, new_data)
        
        assert len(diff.changes) == 1
        assert diff.changes[0].change_type == "added"
    
    def test_detect_annual_fee_change(self):
        """Test detecting fee changes."""
        old_data = {
            "card_name": "Test Card",
            "annual_fee": 95,
            "bank_name": "Test"
        }
        
        new_data = {
            "card_name": "Test Card",
            "annual_fee": 100,  # Changed
            "bank_name": "Test"
        }
        
        diff = ChangeComparator.compare(old_data, new_data)
        
        assert len(diff.changes) == 1
        assert diff.changes[0].field_name == "annual_fee"
        assert diff.changes[0].old_value == 95
        assert diff.changes[0].new_value == 100
        assert diff.changes[0].severity == "critical"
    
    def test_no_changes(self):
        """Test when data hasn't changed."""
        data = {"card_name": "Test", "annual_fee": 95}
        
        diff = ChangeComparator.compare(data.copy(), data.copy())
        
        assert len(diff.changes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
