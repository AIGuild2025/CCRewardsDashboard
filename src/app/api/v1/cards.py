"""Card management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.banks import get_bank_logo_url
from app.core.errors import get_error
from app.models.card import Card
from app.models.statement import Statement
from app.models.user import User
from app.repositories.card import CardRepository
from app.schemas.card import (
    CardDetailResponse,
    CardListResult,
    CardResponse,
    CardUpdateRequest,
)
from app.schemas.statement import (
    MoneyMeta,
    PaginationMeta,
    StatementListResponse,
    StatementListResult,
)

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get(
    "",
    response_model=CardListResult,
    summary="List user's cards",
    description="""
    Get all credit cards for the authenticated user.
    
    Returns basic card information including:
    - Last 4 digits
    - Bank code
    - Card network (if available)
    - Active status
    """,
)
async def list_cards(
    active_only: bool = Query(
        False,
        description="When true, return only active cards.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CardListResult:
    """
    List all cards for the authenticated user.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of cards with total count
    """
    repo = CardRepository(db)
    cards = (
        await repo.get_active_cards_by_user(current_user.id)
        if active_only
        else await repo.get_all_by_user(current_user.id)
    )

    return CardListResult(
        cards=[
            CardResponse.model_validate(card).model_copy(
                update={"bank_logo_url": get_bank_logo_url(card.bank_code)}
            )
            for card in cards
        ],
        total=len(cards),
    )


@router.get(
    "/{card_id}",
    response_model=CardDetailResponse,
    summary="Get card details",
    description="""
    Get detailed information about a specific card including statistics.
    
    Statistics include:
    - Total number of statements
    - Total reward points earned
    - Date of most recent statement
    """,
    responses={
        404: {"description": "Card not found"},
        403: {"description": "Access denied"},
    },
)
async def get_card_detail(
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CardDetailResponse:
    """
    Get detailed card information with statistics.

    Args:
        card_id: Card ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Card details with statistics

    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    repo = CardRepository(db)
    card = await repo.get_by_id(card_id)

    if not card:
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
    if card.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Calculate statistics
    stats_query = select(
        func.count(Statement.id).label("statements_count"),
        func.sum(Statement.reward_points_earned).label("total_reward_points_earned"),
        func.max(Statement.created_at).label("latest_statement_date"),
    ).where(
        Statement.card_id == card_id,
        Statement.deleted_at.is_(None),
    )

    stats_result = await db.execute(stats_query)
    stats = stats_result.one()

    latest_points_query = (
        select(Statement.reward_points)
        .where(
            Statement.card_id == card_id,
            Statement.deleted_at.is_(None),
        )
        .order_by(Statement.statement_month.desc(), Statement.created_at.desc())
        .limit(1)
    )
    latest_points_result = await db.execute(latest_points_query)
    latest_reward_points = latest_points_result.scalar_one_or_none() or 0

    return CardDetailResponse(
        id=card.id,
        last_four=card.last_four,
        bank_code=card.bank_code,
        network=card.network,
        product_name=card.product_name,
        is_active=card.is_active,
        bank_logo_url=get_bank_logo_url(card.bank_code),
        created_at=card.created_at,
        updated_at=card.updated_at,
        statements_count=stats.statements_count or 0,
        total_reward_points=latest_reward_points,
        latest_statement_date=stats.latest_statement_date,
    )


@router.patch(
    "/{card_id}",
    response_model=CardResponse,
    summary="Update card status",
    description="""
    Update card information (currently only active status).
    
    Use this to mark cards as inactive when they are:
    - Cancelled by the bank
    - No longer in use
    - Lost or stolen
    """,
    responses={
        404: {"description": "Card not found"},
        403: {"description": "Access denied"},
    },
)
async def update_card(
    card_id: UUID,
    update_data: CardUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CardResponse:
    """
    Update card information.

    Args:
        card_id: Card ID
        update_data: Update data
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated card information

    Raises:
        HTTPException: 404 if not found, 403 if access denied
    """
    repo = CardRepository(db)
    card = await repo.get_by_id(card_id)

    if not card:
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
    if card.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Update card
    card.is_active = update_data.is_active
    await db.commit()
    await db.refresh(card)

    return CardResponse.model_validate(card)


@router.get(
    "/{card_id}/statements",
    response_model=StatementListResult,
    summary="Get card's statements",
    description="""
    Get all statements for a specific card with pagination.
    
    Returns statements ordered by statement month (newest first).
    """,
    responses={
        404: {"description": "Card not found"},
        403: {"description": "Access denied"},
    },
)
async def get_card_statements(
    card_id: UUID,
    page: Annotated[int, "Page number (1-indexed)"] = 1,
    limit: Annotated[int, "Items per page (1-100)"] = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatementListResult:
    """
    Get all statements for a card with pagination.

    Args:
        card_id: Card ID
        page: Page number (1-indexed)
        limit: Items per page
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of statements

    Raises:
        HTTPException: 404 if card not found, 403 if access denied
    """
    # Verify card exists and user has access
    repo = CardRepository(db)
    card = await repo.get_by_id(card_id)

    if not card:
        error_def = get_error("API_003")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "API_003",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    if card.user_id != current_user.id:
        error_def = get_error("API_004")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "API_004",
                "user_message": error_def["user_message"],
                "suggestion": error_def["suggestion"],
            },
        )

    # Get total count
    count_query = (
        select(func.count())
        .select_from(Statement)
        .where(
            Statement.card_id == card_id,
            Statement.deleted_at.is_(None),
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get statements
    offset = (page - 1) * limit
    query = (
        select(Statement)
        .where(
            Statement.card_id == card_id,
            Statement.deleted_at.is_(None),
        )
        .order_by(Statement.statement_month.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    statements = result.scalars().all()

    # Build response
    statement_responses = []
    for stmt in statements:
        statement_responses.append(
            StatementListResponse(
                id=stmt.id,
                card_id=stmt.card_id,
                card_last_four=card.last_four,
                bank_code=card.bank_code,
                statement_month=stmt.statement_month,
                closing_balance=stmt.closing_balance,
                reward_points=stmt.reward_points,
                transactions_count=0,  # Will be calculated if needed
                created_at=stmt.created_at,
            )
        )

    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return StatementListResult(
        statements=statement_responses,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
        ),
        money=MoneyMeta(
            currency=settings.currency, minor_unit=settings.currency_minor_unit
        ),
    )
