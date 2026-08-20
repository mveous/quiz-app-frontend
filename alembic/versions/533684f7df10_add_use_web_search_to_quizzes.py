"""add use_web_search to quizzes

Revision ID: 533684f7df10
Revises: b75d6d8b6c99
Create Date: 2026-07-13 00:58:22.044510

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '533684f7df10'
down_revision: Union[str, None] = 'b75d6d8b6c99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'quizzes',
        sa.Column('use_web_search', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('quizzes', 'use_web_search', server_default=None)


def downgrade() -> None:
    op.drop_column('quizzes', 'use_web_search')
