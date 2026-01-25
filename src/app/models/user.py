"""User model for authentication and data ownership."""
from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """User model representing authenticated users."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="user", lazy="selectin")
    statements: Mapped[list["Statement"]] = relationship("Statement", back_populates="user", lazy="selectin")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, is_active={self.is_active})>"
