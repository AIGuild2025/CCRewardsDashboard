"""Pydantic schemas for card API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CardResponse(BaseModel):
    """Card data for API responses."""

    id: UUID
    last_four: str = Field(description="Last 4 digits of card number")
    bank_code: str = Field(description="Bank identifier code")
    network: str | None = Field(None, description="Card network (Visa, Mastercard, etc.)")
    product_name: str | None = Field(None, description="Card product name")
    is_active: bool = Field(description="Whether card is active")
    created_at: datetime = Field(description="Card creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class CardDetailResponse(BaseModel):
    """Detailed card information with statistics."""

    id: UUID
    last_four: str = Field(description="Last 4 digits of card number")
    bank_code: str = Field(description="Bank identifier code")
    network: str | None = Field(None, description="Card network (Visa, Mastercard, etc.)")
    product_name: str | None = Field(None, description="Card product name")
    is_active: bool = Field(description="Whether card is active")
    created_at: datetime = Field(description="Card creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Statistics
    statements_count: int = Field(description="Total number of statements")
    total_reward_points: int = Field(default=0, description="Total reward points across all statements")
    latest_statement_date: datetime | None = Field(None, description="Date of most recent statement")

    model_config = ConfigDict(from_attributes=True)


class CardListResult(BaseModel):
    """Paginated list of cards."""

    cards: list[CardResponse]
    total: int = Field(description="Total number of cards")

    model_config = ConfigDict(from_attributes=True)
