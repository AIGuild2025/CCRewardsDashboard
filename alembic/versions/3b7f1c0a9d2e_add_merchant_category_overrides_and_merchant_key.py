"""Add merchant_key to transactions and merchant_category_overrides table.

Revision ID: 3b7f1c0a9d2e
Revises: 1c2d3e4f5a6b
Create Date: 2026-01-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3b7f1c0a9d2e"
down_revision: Union[str, None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add merchant_key to transactions (nullable for existing rows).
    op.add_column("transactions", sa.Column("merchant_key", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_transactions_user_id_merchant_key",
        "transactions",
        ["user_id", "merchant_key"],
        unique=False,
    )

    # Best-effort backfill for existing rows where merchant is present.
    # Normalization: trim, collapse whitespace, uppercase.
    op.execute(
        sa.text(
            r"""
            UPDATE transactions
            SET merchant_key = UPPER(REGEXP_REPLACE(BTRIM(merchant), '\s+', ' ', 'g'))
            WHERE merchant IS NOT NULL AND merchant_key IS NULL
            """
        )
    )

    # 2) Create overrides table (user-scoped).
    op.create_table(
        "merchant_category_overrides",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_key", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "merchant_key", name="uq_override_user_merchant_key"
        ),
    )
    op.create_index(
        "ix_override_user_merchant_key",
        "merchant_category_overrides",
        ["user_id", "merchant_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_override_user_merchant_key", table_name="merchant_category_overrides")
    op.drop_table("merchant_category_overrides")

    op.drop_index("ix_transactions_user_id_merchant_key", table_name="transactions")
    op.drop_column("transactions", "merchant_key")

