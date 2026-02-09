"""add earnings tables

Revision ID: 20250914_add_earnings_tables
Revises: 20250911_add_document_metadata
Create Date: 2025-09-14 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250914_add_earnings_tables'
down_revision = '20250911_add_document_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # earnings_events
    op.create_table(
        'earnings_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('ticker', sa.String(length=32), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('time_of_day', sa.String(length=8), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_earnings_events_ticker', 'earnings_events', ['ticker'])
    op.create_index('ix_earnings_events_event_date', 'earnings_events', ['event_date'])

    # highlights
    op.create_table(
        'highlights',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('ticker', sa.String(length=32), nullable=False),
        sa.Column('doc_id', sa.String(length=64), nullable=True),
        sa.Column('summary_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rank_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['doc_id'], ['documents.id'], name='fk_highlights_doc', ondelete='SET NULL'),
    )
    op.create_index('ix_highlights_ticker', 'highlights', ['ticker'])
    op.create_index('ix_highlights_doc_id', 'highlights', ['doc_id'])
    op.create_index('ix_highlights_created_at', 'highlights', ['created_at'])

    # watchlist
    op.create_table(
        'watchlist',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=True),
        sa.Column('ticker', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_watchlist_user_id', 'watchlist', ['user_id'])
    op.create_index('ix_watchlist_ticker', 'watchlist', ['ticker'])


def downgrade() -> None:
    op.drop_index('ix_watchlist_ticker', table_name='watchlist')
    op.drop_index('ix_watchlist_user_id', table_name='watchlist')
    op.drop_table('watchlist')

    op.drop_index('ix_highlights_created_at', table_name='highlights')
    op.drop_index('ix_highlights_doc_id', table_name='highlights')
    op.drop_index('ix_highlights_ticker', table_name='highlights')
    op.drop_table('highlights')

    op.drop_index('ix_earnings_events_event_date', table_name='earnings_events')
    op.drop_index('ix_earnings_events_ticker', table_name='earnings_events')
    op.drop_table('earnings_events')
