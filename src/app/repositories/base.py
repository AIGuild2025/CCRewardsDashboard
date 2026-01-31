"""Base repository with generic CRUD operations."""
from typing import Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Generic repository providing CRUD operations for any model."""

    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    async def get_by_id(self, id: UUID) -> T | None:
        """Get a single record by ID."""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Get multiple records with pagination."""
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, obj: T) -> T:
        """Create a new record."""
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, id: UUID, data: dict) -> T | None:
        """Update a record by ID with provided data."""
        obj = await self.get_by_id(id)
        if not obj:
            return None

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID."""
        obj = await self.get_by_id(id)
        if not obj:
            return False

        await self.db.delete(obj)
        await self.db.commit()
        return True
