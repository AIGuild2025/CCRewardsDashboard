"""Card service for business logic operations."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.repositories.card import CardRepository


class CardService:
    """Service layer for card-related operations."""

    def __init__(self, db: AsyncSession):
        """Initialize card service with database session.

        Args:
            db: Database session
        """
        self.db = db
        self.card_repo = CardRepository(db)

    async def get_user_cards(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Card]:
        """Get all cards for a user with pagination.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of cards belonging to the user
        """
        return await self.card_repo.get_all_by_user(user_id, skip, limit)

    async def get_card_by_id(self, user_id: UUID, card_id: UUID) -> Card | None:
        """Get a specific card for a user.

        Args:
            user_id: User ID
            card_id: Card ID

        Returns:
            Card if found and belongs to user, None otherwise
        """
        return await self.card_repo.get_by_user(user_id, card_id)

    async def get_active_cards(self, user_id: UUID) -> list[Card]:
        """Get only active cards for a user.

        Args:
            user_id: User ID

        Returns:
            List of active cards
        """
        return await self.card_repo.get_active_cards_by_user(user_id)

    async def deactivate_card(self, user_id: UUID, card_id: UUID) -> Card | None:
        """Deactivate a card for a user.

        Args:
            user_id: User ID
            card_id: Card ID

        Returns:
            Deactivated card if found and belongs to user, None otherwise
        """
        return await self.card_repo.deactivate(user_id, card_id)
