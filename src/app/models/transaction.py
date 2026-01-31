"""Transaction model representing individual transactions within statements."""
from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Transaction(BaseModel):
    """Transaction model representing individual credit card transactions."""

    __tablename__ = "transactions"

    statement_id: Mapped[UUID] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merchant_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_credit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_transactions_user_id_merchant_key", "user_id", "merchant_key"),
    )

    # Relationships
    statement: Mapped["Statement"] = relationship("Statement", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, merchant={self.merchant}, amount={self.amount})>"
