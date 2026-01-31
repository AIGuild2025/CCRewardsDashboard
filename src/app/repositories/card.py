"""Card repository with user-scoped queries."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.repositories.base import BaseRepository


class CardRepository(BaseRepository[Card]):
    """Repository for Card model with user-scoped security."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Card)

    async def get_by_user(self, user_id: UUID, card_id: UUID) -> Card | None:
        """Get card only if it belongs to the specified user."""
        result = await self.db.execute(
            select(Card).where(Card.id == card_id, Card.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Card]:
        """Get all cards for a specific user with pagination."""
        result = await self.db.execute(
            select(Card).where(Card.user_id == user_id).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_cards_by_user(self, user_id: UUID) -> list[Card]:
        """Get only active cards for a user."""
        result = await self.db.execute(
            select(Card).where(Card.user_id == user_id, Card.is_active == True)
        )
        return list(result.scalars().all())

    async def get_by_last_four_and_bank(
        self, user_id: UUID, last_four: str, bank_code: str
    ) -> Card | None:
        """
        Find card by last 4 digits and bank code for a user.
        Used during PDF statement parsing to match the card.
        """
        result = await self.db.execute(
            select(Card).where(
                Card.user_id == user_id,
                Card.last_four == last_four,
                Card.bank_code == bank_code,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_bank(self, user_id: UUID, bank_code: str) -> list[Card]:
        """Get all cards from a specific bank for a user."""
        result = await self.db.execute(
            select(Card).where(Card.user_id == user_id, Card.bank_code == bank_code)
        )
        return list(result.scalars().all())

    async def deactivate(self, user_id: UUID, card_id: UUID) -> Card | None:
        """Soft delete card by setting is_active to False."""
        card = await self.get_by_user(user_id, card_id)
        if not card:
            return None
        return await self.update(card_id, {"is_active": False})
