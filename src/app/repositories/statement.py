"""Statement repository with user-scoped queries and relationship loading."""
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.statement import Statement
from app.repositories.base import BaseRepository


class StatementRepository(BaseRepository[Statement]):
    """Repository for Statement model with user-scoped security and relationship loading."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Statement)

    async def get_by_user(self, user_id: UUID, statement_id: UUID) -> Statement | None:
        """Get statement only if it belongs to the specified user."""
        result = await self.db.execute(
            select(Statement)
            .options(joinedload(Statement.card))  # Avoid N+1 queries
            .where(Statement.id == statement_id, Statement.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Statement]:
        """Get all statements for a user with pagination."""
        result = await self.db.execute(
            select(Statement)
            .options(joinedload(Statement.card))
            .where(Statement.user_id == user_id)
            .order_by(Statement.statement_month.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_card_and_month(
        self, user_id: UUID, card_id: UUID, statement_month: date
    ) -> Statement | None:
        """
        Check if statement already exists for a card and month.
        Used before uploading to prevent duplicates.
        """
        result = await self.db.execute(
            select(Statement).where(
                Statement.user_id == user_id,
                Statement.card_id == card_id,
                Statement.statement_month == statement_month,
            )
        )
        return result.scalar_one_or_none()

    async def get_statements_by_card(
        self, user_id: UUID, card_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Statement]:
        """Get all statements for a specific card."""
        result = await self.db.execute(
            select(Statement)
            .where(Statement.user_id == user_id, Statement.card_id == card_id)
            .order_by(Statement.statement_month.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[Statement]:
        """Get statements within a date range."""
        result = await self.db.execute(
            select(Statement)
            .options(joinedload(Statement.card))
            .where(
                Statement.user_id == user_id,
                Statement.statement_month >= start_date,
                Statement.statement_month <= end_date,
            )
            .order_by(Statement.statement_month.desc())
        )
        return list(result.scalars().all())

    async def get_latest_by_card(self, user_id: UUID, card_id: UUID) -> Statement | None:
        """Get the most recent statement for a card."""
        result = await self.db.execute(
            select(Statement)
            .where(Statement.user_id == user_id, Statement.card_id == card_id)
            .order_by(Statement.statement_month.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def soft_delete(self, statement_id: UUID) -> None:
        """Soft delete a statement by setting deleted_at timestamp."""
        from datetime import datetime, timezone
        
        statement = await self.get_by_id(statement_id)
        if statement:
            statement.deleted_at = datetime.now(timezone.utc)
            await self.db.commit()
