"""Statement model representing monthly credit card statements."""
from typing import Any
from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Statement(BaseModel):
    """Statement model representing a monthly credit card statement."""

    __tablename__ = "statements"
    __table_args__ = (UniqueConstraint("card_id", "statement_month", name="uq_card_statement_month"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    # Schema alignment (processing.md Section 6): statements are authoritative and store a masked JSON payload.
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="credit_card_statement",
        server_default=text("'credit_card_statement'"),
    )
    source_bank: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
        index=True,
    )
    statement_period: Mapped[date] = mapped_column(Date, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SUCCESS",
        server_default=text("'SUCCESS'"),
    )
    masked_content: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    statement_month: Mapped[date] = mapped_column(Date, nullable=False)
    closing_balance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reward_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="statements")
    card: Mapped["Card"] = relationship("Card", back_populates="statements")
    # Rely on DB-level ON DELETE CASCADE; prevent SQLAlchemy from NULLing FKs on delete.
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="statement",
        lazy="selectin",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"<Statement(id={self.id}, card_id={self.card_id}, month={self.statement_month})>"
