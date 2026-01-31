"""Transaction repository with filtering and aggregation queries."""
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for Transaction model with filtering and analytics queries."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Transaction)

    async def get_by_statement(
        self, user_id: UUID, statement_id: UUID, skip: int = 0, limit: int = 1000
    ) -> list[Transaction]:
        """Get all transactions for a specific statement."""
        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id, Transaction.statement_id == statement_id
            )
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        """Get all transactions for a user with pagination."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_category(
        self, user_id: UUID, category: str, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        """Get all transactions in a specific category."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.category == category)
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[Transaction]:
        """Get transactions within a date range."""
        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.txn_date >= start_date,
                Transaction.txn_date <= end_date,
            )
            .order_by(Transaction.txn_date.desc())
        )
        return list(result.scalars().all())

    async def get_by_merchant(
        self, user_id: UUID, merchant: str, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        """Get all transactions for a specific merchant."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.merchant.ilike(f"%{merchant}%"))
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_total_spent_by_category(self, user_id: UUID) -> dict[str, int]:
        """
        Aggregate total spending by category.
        Returns dict of {category: total_amount}.
        """
        result = await self.db.execute(
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(Transaction.user_id == user_id, Transaction.is_credit == False)
            .group_by(Transaction.category)
        )
        return {row.category or "Uncategorized": int(row.total) for row in result}

    async def get_total_rewards_earned(self, user_id: UUID) -> int:
        """Calculate total reward points earned by user."""
        result = await self.db.execute(
            select(func.sum(Transaction.reward_points)).where(
                Transaction.user_id == user_id
            )
        )
        total = result.scalar_one_or_none()
        return int(total) if total else 0

    async def get_monthly_spending(
        self, user_id: UUID, year: int, month: int
    ) -> dict[str, int]:
        """
        Get spending breakdown by category for a specific month.
        Returns dict of {category: total_amount}.
        """
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        result = await self.db.execute(
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(
                Transaction.user_id == user_id,
                Transaction.is_credit == False,
                Transaction.txn_date >= start_date,
                Transaction.txn_date < end_date,
            )
            .group_by(Transaction.category)
        )
        return {row.category or "Uncategorized": int(row.total) for row in result}

    async def get_debits_only(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        """Get only debit transactions (purchases)."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.is_credit == False)
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_credits_only(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        """Get only credit transactions (payments, refunds)."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.is_credit == True)
            .order_by(Transaction.txn_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def soft_delete(self, transaction_id: UUID) -> None:
        """Soft delete a transaction by setting deleted_at timestamp."""
        from datetime import datetime, timezone
        
        transaction = await self.get_by_id(transaction_id)
        if transaction:
            transaction.deleted_at = datetime.now(timezone.utc)
            await self.db.commit()
