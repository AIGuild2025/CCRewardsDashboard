"""Pydantic schemas for statement processing and API responses.

This module defines request/response models for the statement service
and API endpoints.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Request schemas


class StatementUploadRequest(BaseModel):
    """Request model for statement upload (not used directly in multipart upload)."""

    password: str | None = Field(None, description="Password for encrypted PDFs")


# Response schemas


class StatementUploadResult(BaseModel):
    """Result of successful statement processing."""

    statement_id: UUID = Field(description="ID of the created statement")
    card_id: UUID = Field(description="ID of the associated card")
    bank: str | None = Field(None, description="Detected bank code")
    statement_month: date = Field(description="Statement period (YYYY-MM-DD)")
    transactions_count: int = Field(description="Number of transactions extracted")
    reward_points: int = Field(default=0, description="Total reward points balance")
    reward_points_earned: int = Field(default=0, description="Reward points earned this period")
    processing_time_ms: int = Field(description="Processing time in milliseconds")

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    """Transaction data for API responses."""

    id: UUID
    txn_date: date = Field(description="Transaction date")
    merchant: str = Field(description="Merchant name (masked)")
    category: str | None = Field(None, description="Transaction category")
    amount: int = Field(description="Amount in cents")
    is_credit: bool = Field(default=False, description="True if credit, False if debit")
    reward_points: int = Field(default=0, description="Reward points earned")

    model_config = ConfigDict(from_attributes=True)


class StatementListResponse(BaseModel):
    """Statement summary for list views."""

    id: UUID
    card_id: UUID = Field(description="Card ID")
    card_last_four: str = Field(description="Last 4 digits of card")
    bank_code: str | None = Field(None, description="Bank identifier")
    statement_month: date = Field(description="Statement period")
    closing_balance: int = Field(description="Closing balance in cents")
    reward_points: int = Field(default=0, description="Total reward points balance")
    reward_points_earned: int = Field(default=0, description="Reward points earned this period")
    transactions_count: int = Field(description="Number of transactions")
    created_at: datetime = Field(description="Upload timestamp")

    model_config = ConfigDict(from_attributes=True)


class StatementDetailResponse(BaseModel):
    """Full statement details including transactions."""

    statement: StatementListResponse
    transactions: list[TransactionResponse]

    model_config = ConfigDict(from_attributes=True)


class CategorySummary(BaseModel):
    """Spending summary for a specific category."""

    category: str = Field(description="Transaction category")
    amount: int = Field(description="Total amount in cents")
    count: int = Field(description="Number of transactions")
    reward_points: int = Field(default=0, description="Total reward points for category")


class MerchantSummary(BaseModel):
    """Top merchant spending summary."""

    merchant: str = Field(description="Merchant name (masked)")
    amount: int = Field(description="Total amount in cents")
    count: int = Field(description="Number of transactions")


class SpendingSummary(BaseModel):
    """Aggregate spending statistics for a statement."""

    total_debit: int = Field(description="Total debit amount in cents")
    total_credit: int = Field(description="Total credit amount in cents")
    net_spending: int = Field(description="Net spending (debit - credit) in cents")
    by_category: list[CategorySummary] = Field(
        default_factory=list, description="Spending breakdown by category"
    )
    top_merchants: list[MerchantSummary] = Field(
        default_factory=list, description="Top merchants by spending"
    )


class StatementDetailWithSummary(BaseModel):
    """Statement detail with spending summary (no transactions)."""

    id: UUID
    card_id: UUID
    card_last_four: str = Field(description="Last 4 digits of card")
    bank_code: str | None = Field(None, description="Bank identifier")
    statement_month: date = Field(description="Statement period")
    closing_balance: int = Field(description="Closing balance in cents")
    reward_points: int = Field(default=0, description="Total reward points")
    transactions_count: int = Field(description="Number of transactions")
    created_at: datetime = Field(description="Upload timestamp")
    spending_summary: SpendingSummary = Field(description="Spending breakdown and statistics")

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(description="Current page number (1-indexed)")
    limit: int = Field(description="Items per page")
    total: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")


class StatementListResult(BaseModel):
    """Paginated list of statements."""

    statements: list[StatementListResponse]
    pagination: PaginationMeta


class TransactionListResult(BaseModel):
    """Paginated list of transactions."""

    transactions: list[TransactionResponse]
    pagination: PaginationMeta


# Error response schemas


class ProcessingErrorDetail(BaseModel):
    """Detailed error information for failed processing."""

    error_code: str = Field(description="Error code from catalog")
    message: str = Field(description="Technical error message (for logging)")
    user_message: str = Field(description="User-friendly error message")
    suggestion: str = Field(description="Actionable guidance")
    retry_allowed: bool = Field(description="Whether the operation can be retried")
    details: dict | None = Field(None, description="Additional context (optional)")


class ProcessingErrorResponse(BaseModel):
    """Error response for failed statement processing."""

    error: ProcessingErrorDetail

    model_config = ConfigDict(from_attributes=True)
