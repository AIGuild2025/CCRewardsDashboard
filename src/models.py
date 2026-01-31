"""
Pydantic models for data validation and schema enforcement
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, validator


class Transaction(BaseModel):
    """Credit card transaction model"""
    
    date: date
    merchant: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0)
    reward_points: Optional[int] = Field(default=0, ge=0)
    category: Optional[str] = None
    transaction_type: Literal["debit", "credit"] = "debit"
    description: Optional[str] = None
    is_reward_eligible: bool = True
    
    # Anonymized fields
    merchant_hash: Optional[str] = None
    location: Optional[str] = None
    
    @validator("amount", pre=True)
    def parse_amount(cls, v):
        """Parse amount from string or number"""
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = v.replace("$", "").replace(",", "").replace("₹", "").strip()
        return Decimal(str(v))
    
    @validator("date", pre=True)
    def parse_date(cls, v):
        """Parse date from various formats"""
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y"]:
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Could not parse date: {v}")


class RewardPoints(BaseModel):
    """Reward points information"""
    
    points_earned: Decimal = Field(default=Decimal("0"), ge=0)
    bonus_points: Decimal = Field(default=Decimal("0"), ge=0)
    points_redeemed: Decimal = Field(default=Decimal("0"), ge=0)
    points_balance: Decimal = Field(default=Decimal("0"), ge=0)
    earning_rate: Optional[str] = None
    expiry_date: Optional[date] = None


class CardMetadata(BaseModel):
    """Credit card metadata"""
    
    issuer: str = Field(..., min_length=1)
    card_type: str  # e.g., "Visa", "Mastercard", "Amex"
    card_product: str  # e.g., "Chase Sapphire Preferred"
    last_four_digits: str = Field(..., pattern=r"^\d{4}$")
    statement_period_start: Optional[date] = None
    statement_period_end: Optional[date] = None
    
    @validator("last_four_digits", pre=True)
    def extract_last_four(cls, v):
        """Extract last 4 digits from card number"""
        if isinstance(v, str):
            # Remove all non-digits
            digits = "".join(filter(str.isdigit, v))
            if len(digits) >= 4:
                return digits[-4:]
        return v


class StatementData(BaseModel):
    """Complete statement extraction result"""
    
    card_metadata: CardMetadata
    transactions: List[Transaction]
    rewards: RewardPoints
    statement_date: date
    total_amount_spent: Decimal = Field(default=Decimal("0"))
    total_credits: Decimal = Field(default=Decimal("0"))
    
    # Processing metadata
    source_file: str
    parser_method: Literal["textract", "unstructured", "pdfplumber"] = "textract"
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @validator("total_amount_spent", always=True)
    def calculate_total_spent(cls, v, values):
        """Calculate total from transactions if not provided"""
        if v == Decimal("0") and "transactions" in values:
            return sum(
                txn.amount for txn in values["transactions"] 
                if txn.transaction_type == "debit"
            )
        return v


class PIIMask(BaseModel):
    """PII masking information for audit trail"""
    
    field_name: str
    original_value: str
    masked_value: str
    mask_method: Literal["hash", "redact", "tokenize"]
    timestamp: datetime = Field(default_factory=datetime.now)


class ParsingResult(BaseModel):
    """Result of PDF parsing operation"""
    
    success: bool
    statement_data: Optional[StatementData] = None
    error_message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    pii_masked_fields: List[PIIMask] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
