"""
Bank-agnostic schema normalization.

Converts bank-specific field names to a universal credit card schema.
Enables cross-bank comparison and aggregation.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CardBenefit(BaseModel):
    """Single benefit."""
    category: str  # e.g., "Travel", "Dining"
    description: str
    bonus_rate: Optional[float] = None  # e.g., 3.0 for 3x


class CardFees(BaseModel):
    """Card fees structure."""
    annual: Optional[float] = None
    foreign_transaction: Optional[float] = None
    late_payment: Optional[float] = None
    cash_advance: Optional[float] = None


class CardNormalized(BaseModel):
    """
    Bank-agnostic credit card schema.
    
    This is the universal format all cards are normalized to.
    """
    card_name: str
    card_id: Optional[str] = None  # Internal identifier
    bank_name: str
    
    # Fees
    annual_fee: Optional[float] = None
    other_fees: Optional[CardFees] = None
    
    # Earning
    base_earning_rate: Optional[float] = None
    category_bonuses: Optional[Dict[str, float]] = None  # {"travel": 3.0, "dining": 2.0}
    bonus_offer: Optional[str] = None  # e.g., "50,000 points on $5k spend"
    
    # Benefits
    benefits: Optional[list[str]] = None
    
    # Requirements
    credit_score_required: Optional[str] = None
    annual_income_required: Optional[str] = None
    
    # Metadata
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "card_name": "Chase Sapphire Preferred",
                "bank_name": "Chase",
                "annual_fee": 95,
                "base_earning_rate": 1.0,
                "category_bonuses": {
                    "travel": 3.0,
                    "dining": 3.0,
                    "other": 1.0
                },
                "benefits": ["3x points on travel and dining", "Trip insurance", "Concierge"],
                "meta": {
                    "source_url": "https://...",
                    "last_updated": "2024-01-30T...",
                    "confidence_score": 0.95,
                    "scraper_version": "v1.0"
                }
            }
        }


class Normalizer:
    """
    Convert bank-specific extracted data to normalized schema.
    """
    
    BANK_MAPPINGS = {
        "chase": {
            "annual_fee": ["annual_fee", "yearly_fee", "annual_charge"],
            "benefits": ["benefits", "perks", "features"],
            "earning_rate": ["earn", "points_rate", "earning"]
        },
        "amex": {
            "annual_fee": ["annual_membership_fee", "yearly_charge"],
            "benefits": ["benefits", "perks"],
            "earning_rate": ["points_per_dollar", "earn"]
        },
        "bofa": {
            "annual_fee": ["annual_fee"],
            "benefits": ["benefits"],
            "earning_rate": ["cash_back", "earning"]
        }
    }
    
    def __init__(self, bank: str):
        """
        Initialize normalizer for specific bank.
        
        Args:
            bank: Bank name (Chase, American Express, etc.)
        """
        self.bank = bank
        self.bank_key = bank.lower().replace(" ", "")[:10]
    
    def normalize(
        self,
        raw_data: Dict[str, Any],
        url: str,
        confidence: float,
        scraper_version: str = "v1.0"
    ) -> CardNormalized:
        """
        Normalize extracted data to universal schema.
        
        Args:
            raw_data: Raw extracted data from any extractor
            url: Source URL
            confidence: Extraction confidence score
            scraper_version: Scraper version
        
        Returns:
            CardNormalized object
        """
        try:
            normalized = CardNormalized(
                card_name=self._extract_card_name(raw_data),
                bank_name=self.bank,
                annual_fee=self._extract_annual_fee(raw_data),
                base_earning_rate=self._extract_base_earning(raw_data),
                category_bonuses=self._extract_category_bonuses(raw_data),
                benefits=self._extract_benefits(raw_data),
                credit_score_required=raw_data.get("credit_score_required"),
                meta={
                    "source_url": url,
                    "last_updated": datetime.utcnow().isoformat(),
                    "confidence_score": confidence,
                    "scraper_version": scraper_version,
                    "bank_name": self.bank
                }
            )
            
            logger.info(f"Normalized {normalized.card_name} from {self.bank}")
            return normalized
        
        except Exception as e:
            logger.error(f"Normalization failed: {e}", exc_info=True)
            raise
    
    def _extract_card_name(self, raw_data: Dict) -> str:
        """Extract card name."""
        name = raw_data.get("card_name", "Unknown Card")
        return name.strip() if isinstance(name, str) else str(name)
    
    def _extract_annual_fee(self, raw_data: Dict) -> Optional[float]:
        """Extract annual fee as float."""
        possible_keys = ["annual_fee", "fees", "annual_charge"]
        
        for key in possible_keys:
            if key in raw_data:
                fee = raw_data[key]
                if isinstance(fee, dict):
                    fee = fee.get("annual")
                if fee:
                    try:
                        # Extract number from string if needed
                        if isinstance(fee, str):
                            import re
                            match = re.search(r'(\d+)', fee.replace(',', ''))
                            return float(match.group(1)) if match else None
                        return float(fee)
                    except:
                        pass
        return None
    
    def _extract_base_earning(self, raw_data: Dict) -> Optional[float]:
        """Extract base earning rate (points per $1 spent)."""
        # Usually base is 1x unless explicitly stated
        earning = raw_data.get("earning_rate", "")
        if isinstance(earning, str) and earning.lower().find("1x") > -1:
            return 1.0
        return 1.0  # Default assumption
    
    def _extract_category_bonuses(self, raw_data: Dict) -> Optional[Dict[str, float]]:
        """Extract category-based earning bonuses."""
        # This is bank-specific parsing
        # For example, "3x on travel and dining" -> {"travel": 3.0, "dining": 3.0}
        bonuses = {}
        
        earning = raw_data.get("earning_rate", "")
        if isinstance(earning, str):
            import re
            # Look for "Nx on <category>"
            matches = re.findall(r'(\d+)x\s+(?:on\s+)?([^,\.]+)', earning, re.IGNORECASE)
            for rate, category in matches:
                category_clean = category.strip().lower()
                bonuses[category_clean] = float(rate)
        
        return bonuses if bonuses else None
    
    def _extract_benefits(self, raw_data: Dict) -> Optional[list[str]]:
        """Extract benefits list."""
        benefits = raw_data.get("benefits")
        
        if not benefits:
            return None
        
        if isinstance(benefits, list):
            return [b.strip() for b in benefits if isinstance(b, str) and b.strip()]
        elif isinstance(benefits, str):
            # Parse comma-separated or newline-separated
            items = benefits.split(',') if ',' in benefits else benefits.split('\n')
            return [item.strip() for item in items if item.strip()]
        
        return None


def normalize(
    raw_data: Dict[str, Any],
    bank: str,
    url: str,
    confidence: float
) -> CardNormalized:
    """
    Convenience function to normalize extraction data.
    
    Args:
        raw_data: Extracted data from any extractor
        bank: Bank name
        url: Source URL
        confidence: Confidence score
    
    Returns:
        Normalized CardNormalized object
    """
    normalizer = Normalizer(bank)
    return normalizer.normalize(raw_data, url, confidence)
