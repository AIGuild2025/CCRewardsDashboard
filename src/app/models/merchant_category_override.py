"""User-specific merchant -> category overrides.

This is intentionally user-scoped (not global) so each user can correct ambiguous
merchant strings without maintaining a global merchant dictionary.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class MerchantCategoryOverride(BaseModel):
    """Override category for a merchant for a specific user."""

    __tablename__ = "merchant_category_overrides"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    merchant_key: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", name="uq_override_user_merchant_key"),
        Index("ix_override_user_merchant_key", "user_id", "merchant_key"),
    )

    user: Mapped["User"] = relationship("User", back_populates="merchant_category_overrides")

    def __repr__(self) -> str:
        return (
            f"<MerchantCategoryOverride(id={self.id}, user_id={self.user_id}, "
            f"merchant_key={self.merchant_key}, category={self.category})>"
        )

