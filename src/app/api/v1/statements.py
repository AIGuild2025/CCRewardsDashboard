"""Statement management endpoints for upload, list, detail, and delete operations."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.errors import get_error
from app.core.exceptions import (
    BankDetectionError,
    DuplicateStatementError,
    MaskingError,
    PDFExtractionError,
    ParsingError,
    StatementProcessingError,
    ValidationError,
)
from app.models.statement import Statement
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.statement import StatementRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.statement import (
    CategorySummary,
    MerchantSummary,
    PaginationMeta,
    ProcessingErrorDetail,
    ProcessingErrorResponse,
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
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
PDF_MAGIC_BYTES = b"%PDF-"
ALLOWED_LIMITS = [10, 20, 50, 100]


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
    - Maximum size: 25MB
    - Supports password-protected PDFs (provide password parameter)

    ## Error Codes
    - PARSE_003: PDF requires password - retry with password
    - PARSE_004: Incorrect password - verify and retry
    - PARSE_001: Unsupported bank format
    - PARSE_006: Duplicate statement already uploaded
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
    file: Annotated[UploadFile, File(description="PDF statement file (max 25MB)")],
    password: Annotated[
        str | None,
        Form(
            description="Optional password for encrypted PDFs. "
            "If PDF is password-protected and no password provided, "
            "response will include error code PARSE_003.",
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
    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        error_def = get_error("API_001")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_001",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Validate content type
    if file.content_type != "application/pdf":
        error_def = get_error("API_001")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_001",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Read file content
    pdf_bytes = await file.read()

    # Validate file size
    if len(pdf_bytes) > MAX_FILE_SIZE:
        error_def = get_error("API_002")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "API_002",
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
        DuplicateStatementError,
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
    query = select(Statement).where(
        and_(Statement.user_id == current_user.id, Statement.deleted_at.is_(None))
    )

    # Apply filters
    if card_id:
        query = query.where(Statement.card_id == card_id)
    if from_date:
        query = query.where(Statement.statement_month >= from_date)
    if to_date:
        query = query.where(Statement.statement_month <= to_date)

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

    # Load the card relationship
    await db.refresh(statement, ["card"])

    # Calculate spending summary
    transaction_repo = TransactionRepository(db)
    transactions = await transaction_repo.get_by_statement(current_user.id, statement_id)

    # Calculate totals
    total_debit = sum(t.amount for t in transactions if not t.is_credit)
    total_credit = sum(t.amount for t in transactions if t.is_credit)
    net_spending = total_debit - total_credit

    # Group by category
    category_map: dict[str, dict] = {}
    for t in transactions:
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

    # Group by merchant (top 10)
    merchant_map: dict[str, dict] = {}
    for t in transactions:
        merchant = t.merchant
        if merchant not in merchant_map:
            merchant_map[merchant] = {"amount": 0, "count": 0}
        merchant_map[merchant]["amount"] += t.amount
        merchant_map[merchant]["count"] += 1

    # Sort merchants by amount, take top 10
    top_merchants = sorted(
        [MerchantSummary(merchant=merch, **data) for merch, data in merchant_map.items()],
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
        transactions_count=len(transactions),
        created_at=statement.created_at,
        spending_summary=summary,
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
    )


@router.delete(
    "/{statement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete statement",
    description="""
    Soft delete a statement. The statement will be hidden but not permanently removed.

    This operation also soft deletes all associated transactions.
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
    Soft delete a statement and its transactions.

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

    # Soft delete statement
    await repo.soft_delete(statement_id)

    # Soft delete all associated transactions
    transaction_repo = TransactionRepository(db)
    transactions = await transaction_repo.get_by_statement(current_user.id, statement_id)
    for transaction in transactions:
        await transaction_repo.soft_delete(transaction.id)

    await db.commit()
