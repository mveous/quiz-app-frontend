"""add grounding and bloom columns

Revision ID: b75d6d8b6c99
Revises: c714a4d233b2
Create Date: 2026-07-11 08:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b75d6d8b6c99'
down_revision: Union[str, None] = 'c714a4d233b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

bloom_level_enum = postgresql.ENUM(
    'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create', name='bloom_level'
)


def upgrade() -> None:
    bloom_level_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('questions', sa.Column('bloom_level', bloom_level_enum, nullable=True))

    op.add_column(
        'quizzes',
        sa.Column('use_my_documents', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('quizzes', 'use_my_documents', server_default=None)


def downgrade() -> None:
    op.drop_column('quizzes', 'use_my_documents')
    op.drop_column('questions', 'bloom_level')
    bloom_level_enum.drop(op.get_bind(), checkfirst=True)
