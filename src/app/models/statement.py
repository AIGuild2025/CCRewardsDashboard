"""Statement model representing monthly credit card statements."""
from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Statement(BaseModel):
    """Statement model representing a monthly credit card statement."""

    __tablename__ = "statements"
    __table_args__ = (UniqueConstraint("card_id", "statement_month", name="uq_card_statement_month"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    statement_month: Mapped[date] = mapped_column(Date, nullable=False)
    closing_balance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="statements")
    card: Mapped["Card"] = relationship("Card", back_populates="statements")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="statement", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Statement(id={self.id}, card_id={self.card_id}, month={self.statement_month})>"
