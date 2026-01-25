"""Transaction query endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.statement import (
    CategorySummary,
    PaginationMeta,
    TransactionListResult,
    TransactionResponse,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=TransactionListResult,
    summary="List transactions with filters",
    description="""
    Query transactions across all statements with powerful filtering options.
    
    ## Filters
    - **card_id**: Filter by specific card
    - **category**: Filter by transaction category
    - **start_date**, **end_date**: Date range filter
    - **min_amount**, **max_amount**: Amount range filter (in cents)
    - **search**: Search merchant names (case-insensitive)
    - **is_credit**: Filter by credit/debit type
    
    ## Sorting
    - Default: by transaction date (newest first)
    - Use **sort_by** parameter: `txn_date`, `-txn_date`, `amount`, `-amount`
    
    Results are paginated with configurable page size.
    """,
)
async def list_transactions(
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page (1-100)")] = 20,
    card_id: Annotated[UUID | None, Query(description="Filter by card ID")] = None,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    start_date: Annotated[
        date | None, Query(description="Filter from date (inclusive)")
    ] = None,
    end_date: Annotated[
        date | None, Query(description="Filter to date (inclusive)")
    ] = None,
    min_amount: Annotated[
        int | None, Query(description="Minimum amount in cents")
    ] = None,
    max_amount: Annotated[
        int | None, Query(description="Maximum amount in cents")
    ] = None,
    search: Annotated[
        str | None, Query(description="Search merchant names")
    ] = None,
    is_credit: Annotated[
        bool | None, Query(description="Filter by credit (True) or debit (False)")
    ] = None,
    sort_by: Annotated[
        str | None,
        Query(
            description="Sort field: txn_date, -txn_date (desc), amount, -amount (desc)"
        ),
    ] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResult:
    """
    List transactions with comprehensive filtering and pagination.

    Args:
        page: Page number (1-indexed)
        limit: Items per page
        card_id: Optional card filter
        category: Optional category filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_amount: Optional minimum amount filter (cents)
        max_amount: Optional maximum amount filter (cents)
        search: Optional merchant search
        is_credit: Optional credit/debit filter
        sort_by: Optional sort field
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of transactions
    """
    # Build base query
    query = select(Transaction).where(
        and_(Transaction.user_id == current_user.id, Transaction.deleted_at.is_(None))
    )

    # Apply filters
    if card_id:
        # Join with Statement to filter by card
        from app.models.statement import Statement

        query = query.join(Statement, Transaction.statement_id == Statement.id).where(
            Statement.card_id == card_id
        )

    if category:
        query = query.where(Transaction.category == category)

    if start_date:
        query = query.where(Transaction.txn_date >= start_date)

    if end_date:
        query = query.where(Transaction.txn_date <= end_date)

    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)

    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)

    if search:
        query = query.where(Transaction.merchant.ilike(f"%{search}%"))

    if is_credit is not None:
        query = query.where(Transaction.is_credit == is_credit)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    if sort_by:
        if sort_by == "txn_date":
            query = query.order_by(Transaction.txn_date.asc())
        elif sort_by == "-txn_date":
            query = query.order_by(Transaction.txn_date.desc())
        elif sort_by == "amount":
            query = query.order_by(Transaction.amount.asc())
        elif sort_by == "-amount":
            query = query.order_by(Transaction.amount.desc())
    else:
        # Default sorting: newest first
        query = query.order_by(Transaction.txn_date.desc())

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    transactions = result.scalars().all()

    # Build response
    transaction_responses = [
        TransactionResponse.model_validate(txn) for txn in transactions
    ]

    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return TransactionListResult(
        transactions=transaction_responses,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/summary",
    response_model=list[CategorySummary],
    summary="Get spending summary by category",
    description="""
    Get aggregated spending statistics grouped by category.
    
    Returns total amount, transaction count, and reward points for each category.
    
    ## Optional Filters
    - **start_date**, **end_date**: Limit summary to date range
    - **card_id**: Limit summary to specific card
    
    Results are sorted by total amount (highest first).
    """,
)
async def get_spending_summary(
    start_date: Annotated[
        date | None, Query(description="Filter from date (inclusive)")
    ] = None,
    end_date: Annotated[
        date | None, Query(description="Filter to date (inclusive)")
    ] = None,
    card_id: Annotated[UUID | None, Query(description="Filter by card ID")] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategorySummary]:
    """
    Get spending summary grouped by category.

    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        card_id: Optional card filter
        current_user: Authenticated user
        db: Database session

    Returns:
        List of category summaries sorted by amount (descending)
    """
    # Build query
    query = (
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("amount"),
            func.count(Transaction.id).label("count"),
            func.sum(Transaction.reward_points).label("reward_points"),
        )
        .where(
            and_(
                Transaction.user_id == current_user.id,
                Transaction.deleted_at.is_(None),
                Transaction.is_credit == False,  # Only debit transactions for spending
            )
        )
        .group_by(Transaction.category)
    )

    # Apply optional filters
    if card_id:
        from app.models.statement import Statement

        query = query.join(Statement, Transaction.statement_id == Statement.id).where(
            Statement.card_id == card_id
        )

    if start_date:
        query = query.where(Transaction.txn_date >= start_date)

    if end_date:
        query = query.where(Transaction.txn_date <= end_date)

    # Execute query
    result = await db.execute(query)
    rows = result.all()

    # Build response
    summaries = [
        CategorySummary(
            category=row.category or "Uncategorized",
            amount=row.amount or 0,
            count=row.count or 0,
            reward_points=row.reward_points or 0,
        )
        for row in rows
    ]

    # Sort by amount (descending)
    summaries.sort(key=lambda x: x.amount, reverse=True)

    return summaries
