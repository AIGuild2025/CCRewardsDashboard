"""Transaction-specific request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class TransactionCategoryOverrideRequest(BaseModel):
    """Request to override a merchant category (user-scoped)."""

    category: str = Field(description="Category to apply (must be from supported taxonomy)")


class TransactionCategoryOverrideResponse(BaseModel):
    """Response after setting a merchant category override."""

    transaction_id: UUID
    merchant: str | None
    merchant_key: str
    category: str
    updated_transactions_count: int = Field(
        description="Number of existing debit transactions updated for this merchant"
    )

