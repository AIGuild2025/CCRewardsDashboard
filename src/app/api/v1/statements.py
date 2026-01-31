"""Statement management endpoints for upload, list, detail, and delete operations."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy import and_, func, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.errors import get_error
from app.core.exceptions import (
    BankDetectionError,
    MaskingError,
    PDFExtractionError,
    ParsingError,
    StatementProcessingError,
    ValidationError,
)
from app.models.card import Card
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.statement import (
    AccountSummary,
    CategorySummary,
    MoneyMeta,
    MerchantSummary,
    PaginationMeta,
    ProcessingErrorDetail,
    ProcessingErrorResponse,
    RewardsSummary,
    SpendingSummary,
    StatementDetailWithSummary,
    StatementListResponse,
    StatementListResult,
    StatementUploadResult,
    TransactionListResult,
    TransactionResponse,
)
from app.services.statement import StatementService

router = APIRouter(prefix="/statements", tags=["statements"])

# Constants
PDF_MAGIC_BYTES = b"%PDF-"
ALLOWED_LIMITS = [10, 20, 50, 100]


def _rewards_summary_from_masked_content(masked_content: dict | None) -> RewardsSummary | None:
    if not masked_content:
        return None
    raw = masked_content.get("rewards_summary")
    if not isinstance(raw, dict):
        return None
    # Accept partial objects; fields are optional.
    return RewardsSummary(**raw)


def _account_summary_from_masked_content(masked_content: dict | None) -> AccountSummary | None:
    if not masked_content:
        return None
    raw = masked_content.get("account_summary")
    if not isinstance(raw, dict):
        return None
    # Account summary fields are required as a group; ignore partials.
    try:
        return AccountSummary(**raw)
    except Exception:
        return None


def create_error_response(error: StatementProcessingError) -> ProcessingErrorResponse:
    """Create error response from exception.

    Args:
        error: Statement processing exception

    Returns:
        Formatted error response
    """
    error_def = get_error(error.error_code)
    return ProcessingErrorResponse(
        error=ProcessingErrorDetail(
            error_code=error.error_code,
            message=error_def["message"],
            user_message=error_def["user_message"],
            suggestion=error_def["suggestion"],
            retry_allowed=error_def["retry_allowed"],
            details=error.details if hasattr(error, "details") else None,
        )
    )


async def trigger_rag_processing(statement_id: UUID, user_id: UUID) -> None:
    """Background task to trigger RAG processing for a statement.

    This will be expanded in future phases to actually process
    embeddings and update vector database.

    Args:
        statement_id: ID of the uploaded statement
        user_id: ID of the user who owns the statement
    """
    # TODO: Phase 10+ - Implement RAG processing
    # - Generate embeddings for transactions
    # - Update vector database
    # - Compute spending patterns
    # - Update statement.rag_status to "READY"
    pass


@router.post(
    "/upload",
    response_model=StatementUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload credit card statement",
    description="""
    Upload and process a credit card statement PDF.

    ## Supported Banks
    - HDFC Bank (India)
    - ICICI Bank (India)
    - SBI (India)
    - American Express (US/India)
    - Citibank (Global)
    - Chase (US)

    ## File Requirements
    - Format: PDF only
    - Request body must be raw PDF bytes (`Content-Type: application/pdf`)
    - Maximum size: configurable via `PDF_MAX_SIZE_MB` (default: 25MB)
    - Supports password-protected PDFs (optional `X-PDF-Password` header)

    ## Error Codes
    - PARSE_003: PDF requires password - retry with password
    - PARSE_004: Incorrect password - verify and retry
    - PARSE_001: Unsupported bank format
    - API_001: Invalid file type
    - API_002: File too large
    - API_005: Invalid PDF file
    """,
    responses={
        201: {"description": "Statement processed successfully"},
        400: {
            "description": "Bad request (invalid file, wrong password, etc.)",
            "model": ProcessingErrorResponse,
        },
        413: {"description": "File too large (max 25MB)"},
        422: {"description": "Validation error"},
    },
)
async def upload_statement(
    background_tasks: BackgroundTasks,
    request: Request,
    password: Annotated[
        str | None,
        Header(
            alias="X-PDF-Password",
            description="Optional password for encrypted PDFs.",
        ),
    ] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatementUploadResult:
    """
    Upload and process a credit card statement.

    The statement is parsed synchronously (3-10 seconds) and then
    RAG processing is triggered in the background.

    Args:
        background_tasks: FastAPI background tasks manager
        file: Uploaded PDF file
        password: Optional password for encrypted PDFs
        current_user: Authenticated user
        db: Database session

    Returns:
        Statement upload result with processing details

    Raises:
        HTTPException: Various status codes for different error conditions
    """
    # Validate content type (raw body upload, no multipart).
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type.lower() != "application/pdf":
        error_def = get_error("API_001")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_001",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Read request body in-memory with a strict size cap (no disk spooling).
    max_bytes = settings.pdf_max_size_mb * 1024 * 1024
    buf = bytearray()
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            error_def = get_error("API_002")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "API_002",
                    "user_message": error_def["user_message"],
                    "suggestion": error_def["suggestion"],
                },
            )
        buf.extend(chunk)
    pdf_bytes = bytes(buf)

    # Validate file size
    if not pdf_bytes:
        error_def = get_error("API_005")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_005",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Validate PDF magic bytes
    if not pdf_bytes.startswith(PDF_MAGIC_BYTES):
        error_def = get_error("API_005")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_005",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Process statement
    try:
        service = StatementService(db)
        result = await service.process_upload(pdf_bytes, current_user, password)

        # Trigger background RAG processing
        background_tasks.add_task(
            trigger_rag_processing, result.statement_id, current_user.id
        )

        return result

    except (
        PDFExtractionError,
        BankDetectionError,
        ParsingError,
        ValidationError,
        MaskingError,
    ) as e:
        error_response = create_error_response(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response.error.model_dump(),
        )


@router.get(
    "",
    response_model=StatementListResult,
    summary="List user's statements",
    description="""
    Get paginated list of user's statements with optional filtering.

    ## Pagination
    - Default page size: 20
    - Available sizes: 10, 20, 50, 100
    - Results sorted by created_at (newest first) by default

    ## Filters
    - card_id: Filter by specific card
    - from_date: Start date (YYYY-MM-DD)
    - to_date: End date (YYYY-MM-DD)
    """,
)
async def list_statements(
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Items per page (1-100)")
    ] = 20,
    card_id: Annotated[UUID | None, Query(description="Filter by card ID")] = None,
    from_date: Annotated[
        date | None, Query(description="Filter statements from date (inclusive)")
    ] = None,
    to_date: Annotated[
        date | None, Query(description="Filter statements to date (inclusive)")
    ] = None,
    include_inactive_cards: Annotated[
        bool,
        Query(
            description="When true, include statements for inactive cards. By default, statements are limited to active cards.",
        ),
    ] = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatementListResult:
    """
    List user's statements with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        limit: Items per page
        card_id: Optional card filter
        from_date: Optional start date filter
        to_date: Optional end date filter
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of statements
    """
    # Build query
    query = (
        select(Statement)
        .join(Card, Statement.card_id == Card.id)
        .where(and_(Statement.user_id == current_user.id, Statement.deleted_at.is_(None)))
    )

    # Apply filters
    if card_id:
        query = query.where(Statement.card_id == card_id)
    if from_date:
        query = query.where(Statement.statement_month >= from_date)
    if to_date:
        query = query.where(Statement.statement_month <= to_date)
    if not include_inactive_cards:
        query = query.where(Card.is_active.is_(True))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * limit
    query = query.order_by(Statement.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    statements = result.scalars().all()

    # Build response
    statement_list = [
        StatementListResponse(
            id=stmt.id,
            card_id=stmt.card_id,
            card_last_four=stmt.card.last_four if stmt.card else "Unknown",
            bank_code=stmt.card.bank_code if stmt.card else None,
            statement_month=stmt.statement_month,
            closing_balance=stmt.closing_balance,
            reward_points=stmt.reward_points,
            reward_points_earned=stmt.reward_points_earned,
            rewards_summary=_rewards_summary_from_masked_content(getattr(stmt, "masked_content", None)),
            account_summary=_account_summary_from_masked_content(getattr(stmt, "masked_content", None)),
            transactions_count=len(stmt.transactions)
            if hasattr(stmt, "transactions")
            else 0,
            created_at=stmt.created_at,
        )
        for stmt in statements
    ]

    total_pages = (total + limit - 1) // limit  # Ceiling division

    return StatementListResult(
        statements=statement_list,
        pagination=PaginationMeta(
            page=page, limit=limit, total=total, total_pages=total_pages
        ),
        money=MoneyMeta(currency=settings.currency, minor_unit=settings.currency_minor_unit),
    )


@router.get(
    "/{statement_id}",
    response_model=StatementDetailWithSummary,
    summary="Get statement detail",
    description="""
    Get detailed information about a specific statement including
    spending summary and category breakdown.

    This endpoint does NOT include individual transactions.
    Use GET /statements/{id}/transactions for transaction list.
    """,
    responses={
        404: {"description": "Statement not found"},
        403: {"description": "Access denied"},
    },
)
async def get_statement_detail(
    statement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatementDetailWithSummary:
    """
    Get statement details with spending summary.

    Args:
        statement_id: Statement ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Statement details with category breakdown

    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    repo = StatementRepository(db)
    statement = await repo.get_by_id(statement_id)

    if not statement or statement.deleted_at is not None:
        error_def = get_error("API_003")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_003",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Check ownership
    if statement.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Load the card relationship
    await db.refresh(statement, ["card"])

    # Calculate spending summary
    transaction_repo = TransactionRepository(db)
    transactions = await transaction_repo.get_by_statement(current_user.id, statement_id)

    # Calculate totals
    total_debit = sum(t.amount for t in transactions if not t.is_credit)
    total_credit = sum(t.amount for t in transactions if t.is_credit)
    net_spending = total_debit - total_credit

    # Fee waivers/reversals often appear as credits with "waiver"/"reversal" in the merchant text.
    fee_waivers_credit = sum(
        t.amount
        for t in transactions
        if t.is_credit
        and (
            "waiver" in (t.merchant or "").lower()
            or "waive" in (t.merchant or "").lower()
            or "reversal" in (t.merchant or "").lower()
            or (t.category or "").lower() == "fees"
        )
    )
    if fee_waivers_credit <= 0:
        fee_waivers_credit = None

    debit_transactions = [t for t in transactions if not t.is_credit]

    # Group by category (debit-only for "expenditure").
    category_map: dict[str, dict] = {}
    for t in debit_transactions:
        category = t.category or "Uncategorized"
        if category not in category_map:
            category_map[category] = {"amount": 0, "count": 0, "reward_points": 0}
        category_map[category]["amount"] += t.amount
        category_map[category]["count"] += 1
        category_map[category]["reward_points"] += t.reward_points

    # Sort categories by amount
    by_category = sorted(
        [
            CategorySummary(category=cat, **data)
            for cat, data in category_map.items()
        ],
        key=lambda x: x.amount,
        reverse=True,
    )

    # Group by merchant (top 10) (debit-only for "expenditure").
    merchant_map: dict[str, dict] = {}
    for t in debit_transactions:
        merchant = t.merchant
        if merchant not in merchant_map:
            merchant_map[merchant] = {"amount": 0, "count": 0, "categories": {}}
        merchant_map[merchant]["amount"] += t.amount
        merchant_map[merchant]["count"] += 1
        cat = t.category or "Uncategorized"
        merchant_map[merchant]["categories"][cat] = (
            merchant_map[merchant]["categories"].get(cat, 0) + t.amount
        )

    # Sort merchants by amount, take top 10
    top_merchants = sorted(
        [
            MerchantSummary(
                merchant=merch,
                amount=data["amount"],
                count=data["count"],
                category=(
                    max(data["categories"].items(), key=lambda kv: kv[1])[0]
                    if data["categories"]
                    else None
                ),
                categories_breakdown=(
                    data["categories"] if len(data["categories"]) > 1 else None
                ),
            )
            for merch, data in merchant_map.items()
        ],
        key=lambda x: x.amount,
        reverse=True,
    )[:10]

    # Build summary
    summary = SpendingSummary(
        total_debit=total_debit,
        total_credit=total_credit,
        net_spending=net_spending,
        by_category=by_category,
        top_merchants=top_merchants,
    )

    return StatementDetailWithSummary(
        id=statement.id,
        card_id=statement.card_id,
        card_last_four=statement.card.last_four if statement.card else "Unknown",
        bank_code=statement.card.bank_code if statement.card else None,
        statement_month=statement.statement_month,
        closing_balance=statement.closing_balance,
        reward_points=statement.reward_points,
        reward_points_earned=statement.reward_points_earned,
        rewards_summary=_rewards_summary_from_masked_content(getattr(statement, "masked_content", None)),
        account_summary=_account_summary_from_masked_content(getattr(statement, "masked_content", None)),
        fee_waivers_credit=fee_waivers_credit,
        transactions_count=len(transactions),
        created_at=statement.created_at,
        spending_summary=summary,
        money=MoneyMeta(currency=settings.currency, minor_unit=settings.currency_minor_unit),
    )


@router.get(
    "/{statement_id}/transactions",
    response_model=TransactionListResult,
    summary="Get statement transactions",
    description="""
    Get paginated list of transactions for a statement with filtering and sorting.

    ## Filters
    - category: Filter by transaction category
    - search: Search merchant names (case-insensitive)
    - from_date: Transaction date start
    - to_date: Transaction date end

    ## Sorting
    - Default: by transaction date (newest first)
    - Available: txn_date, -txn_date, amount, -amount
    """,
    responses={
        404: {"description": "Statement not found"},
        403: {"description": "Access denied"},
    },
)
async def list_transactions(
    statement_id: UUID,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    limit: Annotated[
        int, Query(ge=10, le=100, description="Items per page (10, 20, 50, 100)")
    ] = 50,
    category: Annotated[
        str | None, Query(description="Filter by category")
    ] = None,
    search: Annotated[
        str | None, Query(description="Search merchant names (case-insensitive)")
    ] = None,
    from_date: Annotated[
        date | None, Query(description="Filter transactions from date")
    ] = None,
    to_date: Annotated[
        date | None, Query(description="Filter transactions to date")
    ] = None,
    sort: Annotated[
        str, Query(description="Sort field: txn_date, -txn_date, amount, -amount")
    ] = "-txn_date",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResult:
    """
    List transactions for a statement with filtering.

    Args:
        statement_id: Statement ID
        page: Page number
        limit: Items per page
        category: Category filter
        search: Merchant search term
        from_date: Start date filter
        to_date: End date filter
        sort: Sort field and direction
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of transactions

    Raises:
        HTTPException: 404 if statement not found, 403 if access denied
    """
    # Verify statement exists and user has access
    repo = StatementRepository(db)
    statement = await repo.get_by_id(statement_id)

    if not statement or statement.deleted_at is not None:
        error_def = get_error("API_003")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_003",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Check ownership
    if statement.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Build query
    query = select(Transaction).where(
        and_(
            Transaction.statement_id == statement_id,
            Transaction.deleted_at.is_(None),
        )
    )

    # Apply filters
    if category:
        query = query.where(Transaction.category == category)
    if search:
        query = query.where(Transaction.merchant.ilike(f"%{search}%"))
    if from_date:
        query = query.where(Transaction.txn_date >= from_date)
    if to_date:
        query = query.where(Transaction.txn_date <= to_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = Transaction.txn_date
    sort_desc = True

    if sort in ["txn_date", "-txn_date"]:
        sort_column = Transaction.txn_date
        sort_desc = sort.startswith("-")
    elif sort in ["amount", "-amount"]:
        sort_column = Transaction.amount
        sort_desc = sort.startswith("-")

    if sort_desc:
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    transactions = result.scalars().all()

    # Build response
    transaction_list = [
        TransactionResponse(
            id=txn.id,
            txn_date=txn.txn_date,
            merchant=txn.merchant,
            category=txn.category,
            amount=txn.amount,
            is_credit=txn.is_credit,
            reward_points=txn.reward_points,
        )
        for txn in transactions
    ]

    total_pages = (total + limit - 1) // limit

    return TransactionListResult(
        transactions=transaction_list,
        pagination=PaginationMeta(
            page=page, limit=limit, total=total, total_pages=total_pages
        ),
        money=MoneyMeta(currency=settings.currency, minor_unit=settings.currency_minor_unit),
    )


@router.delete(
    "/{statement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete statement",
    description="""
    Permanently delete a statement and its transactions.

    This operation is irreversible.
    """,
    responses={
        204: {"description": "Statement deleted successfully"},
        404: {"description": "Statement not found"},
        403: {"description": "Access denied"},
    },
)
async def delete_statement(
    statement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a statement and its transactions.

    Args:
        statement_id: Statement ID to delete
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    repo = StatementRepository(db)
    statement = await repo.get_by_id(statement_id)

    if not statement:
        error_def = get_error("API_003")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_003",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Check ownership
    if statement.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Hard delete in all cases. Use a SQL DELETE to rely on DB-level ON DELETE CASCADE.
    await db.execute(sa_delete(Statement).where(Statement.id == statement.id))
    await db.commit()
