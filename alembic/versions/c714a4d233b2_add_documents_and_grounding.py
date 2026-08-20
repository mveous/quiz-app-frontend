"""add documents and grounding

Revision ID: c714a4d233b2
Revises: 16071d93d095
Create Date: 2026-07-11 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c714a4d233b2'
down_revision: Union[str, None] = '16071d93d095'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('documents',
    sa.Column('owner_user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('source_type', sa.Enum('pasted_text', 'txt_upload', 'pdf_upload', name='document_source_type'), nullable=False),
    sa.Column('status', sa.Enum('processing', 'ready', 'failed', name='document_status'), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('char_count', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_owner_user_id'), 'documents', ['owner_user_id'], unique=False)

    op.add_column('document_chunks', sa.Column('document_id', sa.UUID(), nullable=False))
    op.add_column('document_chunks', sa.Column('owner_user_id', sa.UUID(), nullable=False))
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_owner_user_id'), 'document_chunks', ['owner_user_id'], unique=False)
    op.create_foreign_key(
        'fk_document_chunks_document_id', 'document_chunks', 'documents', ['document_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_document_chunks_owner_user_id', 'document_chunks', 'users', ['owner_user_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_document_chunks_owner_user_id', 'document_chunks', type_='foreignkey')
    op.drop_constraint('fk_document_chunks_document_id', 'document_chunks', type_='foreignkey')
    op.drop_index(op.f('ix_document_chunks_owner_user_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_column('document_chunks', 'owner_user_id')
    op.drop_column('document_chunks', 'document_id')

    op.drop_index(op.f('ix_documents_owner_user_id'), table_name='documents')
    op.drop_table('documents')
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS document_source_type")
