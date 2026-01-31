"""Align statements schema to processing.md Section 6.

Revision ID: 1c2d3e4f5a6b
Revises: 08bad76148b6
Create Date: 2026-01-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, None] = "08bad76148b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns (nullable first where we need to backfill).
    op.add_column(
        "statements",
        sa.Column(
            "document_type",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'credit_card_statement'"),
        ),
    )
    op.add_column(
        "statements",
        sa.Column(
            "source_bank",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column(
        "statements",
        sa.Column("statement_period", sa.Date(), nullable=True),
    )
    op.add_column(
        "statements",
        sa.Column(
            "ingestion_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'SUCCESS'"),
        ),
    )
    op.add_column(
        "statements",
        sa.Column(
            "masked_content",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )

    # Backfill statement_period (first day of month) from statement_month.
    op.execute(
        "UPDATE statements SET statement_period = statement_month WHERE statement_period IS NULL"
    )
    op.alter_column("statements", "statement_period", nullable=False)

    # Backfill source_bank from cards.bank_code when possible.
    # (Cards are created per-user; bank_code is not PII.)
    op.execute(
        """
        UPDATE statements
        SET source_bank = lower(cards.bank_code)
        FROM cards
        WHERE statements.card_id = cards.id
        """
    )

    op.create_index(op.f("ix_statements_source_bank"), "statements", ["source_bank"])


def downgrade() -> None:
    op.drop_index(op.f("ix_statements_source_bank"), table_name="statements")
    op.drop_column("statements", "masked_content")
    op.drop_column("statements", "ingestion_status")
    op.drop_column("statements", "statement_period")
    op.drop_column("statements", "source_bank")
    op.drop_column("statements", "document_type")
