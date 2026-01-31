"""Internal data schemas for parsed PDF data.

These models represent the intermediate parsed data structure
before PII masking and database persistence.
"""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class ParsedTransaction(BaseModel):
    """Represents a single transaction extracted from a statement.
    
    All amounts are in the smallest currency unit (paise for INR, cents for USD).
    Contains unmasked data that may include PII.
    """

    transaction_date: date = Field(..., description="Transaction date")
    description: str = Field(..., description="Merchant name (may contain PII)")
    amount_cents: int = Field(..., description="Amount in paise/cents (positive for debits)")
    transaction_type: str = Field(default="debit", description="'debit' or 'credit'")
    category: str | None = Field(None, description="Merchant category (if available)")
    
    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Ensure merchant name is not empty."""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()
    
    @classmethod
    def from_decimal(
        cls,
        transaction_date: date,
        description: str,
        amount_decimal: Decimal,
        transaction_type: str = "debit",
        category: str | None = None,
    ) -> "ParsedTransaction":
        """Create from decimal amount (e.g., 1234.56 -> 123456 cents)."""
        amount_cents = int(amount_decimal * 100)
        return cls(
            transaction_date=transaction_date,
            description=description,
            amount_cents=amount_cents,
            transaction_type=transaction_type,
            category=category,
        )


class ParsedAccountSummary(BaseModel):
    """Represents the 'Account Summary' section (when available).

    All amounts are in the smallest currency unit (paise for INR, cents for USD).
    """

    previous_balance_cents: int = Field(description="Previous balance (minor units)")
    credits_cents: int = Field(
        description="Payments, reversals & other credits (minor units)"
    )
    debits_cents: int = Field(description="Purchases & other debits (minor units)")
    fees_cents: int = Field(description="Fees, taxes & interest charges (minor units)")
    total_outstanding_cents: int = Field(description="Total outstanding (minor units)")


class ParsedStatement(BaseModel):
    """Represents a complete parsed credit card statement.
    
    This is the output of the parser before PII masking.
    Contains potentially sensitive information that must be masked before persistence.
    """

    card_last_four: str = Field(..., description="Last 4 digits of card number")
    statement_month: date = Field(..., description="Statement period (first day of month)")
    closing_balance_cents: int = Field(..., description="Statement closing balance in cents")
    reward_points: int = Field(default=0, description="Total reward points balance (accumulated)")
    reward_points_earned: int = Field(default=0, description="Reward points earned this period")
    reward_points_previous: int | None = Field(
        None, description="Reward points previous balance (if available)"
    )
    reward_points_redeemed: int | None = Field(
        None, description="Reward points redeemed/expired/forfeited this period (if available)"
    )
    account_summary: ParsedAccountSummary | None = Field(
        None, description="Account summary section (bank-specific; when available)"
    )
    transactions: list[ParsedTransaction] = Field(
        default_factory=list,
        description="List of transactions"
    )
    
    # Optional metadata
    bank_code: str | None = Field(None, description="Detected bank code (hdfc, icici, etc.)")
    statement_date: date | None = Field(None, description="Statement generation date")
    due_date: date | None = Field(None, description="Payment due date")
    minimum_due_cents: int | None = Field(None, description="Minimum payment due in cents")
    
    @field_validator("card_last_four")
    @classmethod
    def validate_last_four(cls, v: str) -> str:
        """Ensure card last four is 4-5 characters (digits or XX prefix for partial card numbers).
        
        Some banks (like SBI) only show last 2 digits (e.g., "XXXX XXXX XXXX XX95"),
        so we store as "XX95" to maintain the format.
        """
        if len(v) not in [4, 5]:
            raise ValueError("Card last four must be 4-5 characters")
        
        # Allow formats like "XX95" or "1234"
        if not (v.isdigit() or (v.startswith("XX") and v[2:].isdigit())):
            raise ValueError("Card last four must be digits or XX prefix with digits")
        
        return v
    
    @classmethod
    def from_decimal_balance(
        cls,
        card_last_four: str,
        statement_month: date,
        closing_balance_decimal: Decimal,
        reward_points: int = 0,
        transactions: list[ParsedTransaction] | None = None,
        **kwargs,
    ) -> "ParsedStatement":
        """Create from decimal balance (e.g., 12345.67 -> 1234567 cents)."""
        closing_balance_cents = int(closing_balance_decimal * 100)
        return cls(
            card_last_four=card_last_four,
            statement_month=statement_month,
            closing_balance_cents=closing_balance_cents,
            reward_points=reward_points,
            transactions=transactions or [],
            **kwargs,
        )
