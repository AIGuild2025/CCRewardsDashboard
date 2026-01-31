"""Schemas for user override configuration (e.g., merchant -> category)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.statement import PaginationMeta


class MerchantCategoryOverrideResponse(BaseModel):
    """Merchant category override response."""

    id: UUID
    merchant_key: str
    category: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantCategoryOverrideListResult(BaseModel):
    """Paginated list of overrides."""

    overrides: list[MerchantCategoryOverrideResponse]
    pagination: PaginationMeta


class MerchantCategoryOverrideDeleteResult(BaseModel):
    """Delete result for an override."""

    id: UUID
    merchant_key: str
    recomputed_transactions_count: int = Field(
        0, description="Number of debit transactions recomputed after override deletion"
    )

