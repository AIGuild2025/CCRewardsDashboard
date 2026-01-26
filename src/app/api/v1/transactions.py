"""Transaction query endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import and_, bindparam, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.categorization.rules import CATEGORIES, categorize, normalize_merchant
from app.config import settings
from app.core.errors import get_error
from app.models.merchant_category_override import MerchantCategoryOverride
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.overrides import (
    MerchantCategoryOverrideDeleteResult,
    MerchantCategoryOverrideListResult,
    MerchantCategoryOverrideResponse,
)
from app.schemas.transaction import (
    TransactionCategoryOverrideRequest,
    TransactionCategoryOverrideResponse,
)
from app.schemas.statement import (
    CategorySummary,
    MoneyMeta,
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
        money=MoneyMeta(currency=settings.currency, minor_unit=settings.currency_minor_unit),
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


@router.put(
    "/{transaction_id}/category",
    response_model=TransactionCategoryOverrideResponse,
    summary="Override merchant category (user-scoped)",
    description="""
    Override the category for a merchant based on an existing transaction.

    - Overrides apply to the authenticated user only
    - Only debit transactions can be overridden (credits like payments/refunds are excluded)
    - The override is applied to matching past debit transactions for immediate trend correction
    """,
    responses={
        200: {"description": "Override saved"},
        400: {"description": "Invalid category or transaction type"},
        404: {"description": "Transaction not found"},
    },
)
async def set_merchant_category_override(
    transaction_id: UUID,
    payload: TransactionCategoryOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionCategoryOverrideResponse:
    category = (payload.category or "").strip().lower()
    if category not in CATEGORIES:
        error_def = get_error("API_007")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_007",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
            Transaction.deleted_at.is_(None),
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        error_def = get_error("API_006")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_006",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    if txn.is_credit:
        error_def = get_error("API_008")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_008",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    merchant = txn.merchant
    if not merchant:
        error_def = get_error("API_009")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_009",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    merchant_key = txn.merchant_key or normalize_merchant(merchant)
    if not merchant_key:
        error_def = get_error("API_009")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_009",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Ensure this transaction has merchant_key for future queries.
    if txn.merchant_key != merchant_key:
        txn.merchant_key = merchant_key
        await db.flush()

    # Upsert override row (revive if previously soft deleted).
    existing = (
        await db.execute(
            select(MerchantCategoryOverride).where(
                MerchantCategoryOverride.user_id == current_user.id,
                MerchantCategoryOverride.merchant_key == merchant_key,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.category = category
        existing.deleted_at = None
    else:
        db.add(
            MerchantCategoryOverride(
                user_id=current_user.id,
                merchant_key=merchant_key,
                category=category,
            )
        )

    # Backfill matching debit transactions so trends update immediately.
    upd = await db.execute(
        update(Transaction)
        .where(
            Transaction.user_id == current_user.id,
            Transaction.deleted_at.is_(None),
            Transaction.is_credit == False,
            Transaction.merchant_key == merchant_key,
        )
        .values(category=category)
    )
    await db.commit()

    return TransactionCategoryOverrideResponse(
        transaction_id=txn.id,
        merchant=txn.merchant,
        merchant_key=merchant_key,
        category=category,
        updated_transactions_count=int(upd.rowcount or 0),
    )


@router.get(
    "/category-overrides",
    response_model=MerchantCategoryOverrideListResult,
    summary="List merchant category overrides",
    description="""
    List user-scoped merchant category overrides.

    These overrides are applied during ingestion and can be used to backfill
    existing transactions for more accurate trends.
    """,
)
async def list_merchant_category_overrides(
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page (1-100)")] = 20,
    search: Annotated[str | None, Query(description="Search by merchant key")] = None,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantCategoryOverrideListResult:
    q = select(MerchantCategoryOverride).where(
        MerchantCategoryOverride.user_id == current_user.id,
        MerchantCategoryOverride.deleted_at.is_(None),
    )

    if search:
        q = q.where(
            MerchantCategoryOverride.merchant_key.ilike(
                f"%{normalize_merchant(search)}%"
            )
        )
    if category:
        q = q.where(MerchantCategoryOverride.category == category.strip().lower())

    # Count first
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Page
    q = q.order_by(MerchantCategoryOverride.updated_at.desc())
    offset = (page - 1) * limit
    q = q.offset(offset).limit(limit)

    overrides = (await db.execute(q)).scalars().all()

    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return MerchantCategoryOverrideListResult(
        overrides=[MerchantCategoryOverrideResponse.model_validate(o) for o in overrides],
        pagination=PaginationMeta(
            page=page, limit=limit, total=total, total_pages=total_pages
        ),
    )


@router.delete(
    "/category-overrides/{override_id}",
    response_model=MerchantCategoryOverrideDeleteResult,
    summary="Delete merchant category override",
    description="""
    Delete a merchant category override.

    If `recompute=true`, the backend recomputes affected debit transactions using
    the deterministic rules fallback (no override, no parser category).
    """,
)
async def delete_merchant_category_override(
    override_id: UUID,
    recompute: Annotated[
        bool, Query(description="Recompute affected debit transactions after delete")
    ] = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantCategoryOverrideDeleteResult:
    ov = (
        await db.execute(
            select(MerchantCategoryOverride).where(
                MerchantCategoryOverride.id == override_id,
                MerchantCategoryOverride.user_id == current_user.id,
                MerchantCategoryOverride.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not ov:
        # Reuse "not found" semantics.
        error_def = get_error("API_006")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_006",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    merchant_key = ov.merchant_key

    recomputed = 0
    if recompute:
        # Fetch affected debit transactions and recompute categories using the
        # deterministic rules fallback.
        txns = (
            await db.execute(
                select(Transaction.id, Transaction.merchant).where(
                    Transaction.user_id == current_user.id,
                    Transaction.deleted_at.is_(None),
                    Transaction.is_credit == False,
                    Transaction.merchant_key == merchant_key,
                )
            )
        ).all()

        params = []
        for txn_id, merchant in txns:
            params.append(
                {
                    "b_id": txn_id,
                    "b_category": categorize(merchant, transaction_type="debit"),
                }
            )
        if params:
            await db.execute(
                update(Transaction.__table__)
                .where(Transaction.__table__.c.id == bindparam("b_id"))
                .values(category=bindparam("b_category")),
                params,
                execution_options={"synchronize_session": False},
            )
            recomputed = len(params)
            # Keep session identity-map consistent for this request.
            db.expire_all()

    # Hard delete the override row.
    await db.delete(ov)
    await db.commit()

    return MerchantCategoryOverrideDeleteResult(
        id=override_id, merchant_key=merchant_key, recomputed_transactions_count=recomputed
    )
