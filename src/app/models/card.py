"""Card model representing credit cards owned by users."""
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Card(BaseModel):
    """Card model representing a credit card."""

    __tablename__ = "cards"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    bank_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    network: Mapped[str | None] = mapped_column(String(20), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="cards")
    statements: Mapped[list["Statement"]] = relationship("Statement", back_populates="card", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Card(id={self.id}, bank={self.bank_code}, last_four={self.last_four})>"
