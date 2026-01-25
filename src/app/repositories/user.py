"""User repository for user-specific queries."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with authentication queries."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        """Find user by email address (used for login)."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        result = await self.db.execute(select(User.id).where(User.email == email))
        return result.scalar_one_or_none() is not None

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all active users with pagination."""
        result = await self.db.execute(
            select(User).where(User.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def deactivate(self, user_id) -> User | None:
        """Soft delete user by setting is_active to False."""
        return await self.update(user_id, {"is_active": False})

    async def activate(self, user_id) -> User | None:
        """Reactivate a deactivated user."""
        return await self.update(user_id, {"is_active": True})
