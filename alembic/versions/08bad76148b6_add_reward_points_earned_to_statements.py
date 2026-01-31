"""add_reward_points_earned_to_statements

Revision ID: 08bad76148b6
Revises: 657c93668050
Create Date: 2026-01-24 18:09:56.683289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08bad76148b6'
down_revision: Union[str, None] = '657c93668050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add reward_points_earned column with default value of 0
    op.add_column('statements', sa.Column('reward_points_earned', sa.Integer(), nullable=False, server_default='0'))
    
    # For existing rows, set reward_points_earned = reward_points (backwards compatibility)
    op.execute('UPDATE statements SET reward_points_earned = reward_points WHERE reward_points_earned = 0')


def downgrade() -> None:
    # Remove the column
    op.drop_column('statements', 'reward_points_earned')
