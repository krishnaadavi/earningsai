"""add guidance insights table

Revision ID: 20250924_add_guidance_insights
Revises: 20250914_add_earnings_tables
Create Date: 2025-09-24 18:41:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250924_add_guidance_insights'
down_revision = '20250914_add_earnings_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'guidance_insights',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('doc_id', sa.String(length=64), nullable=False),
        sa.Column('metric', sa.String(length=64), nullable=True),
        sa.Column('period', sa.String(length=32), nullable=True),
        sa.Column('value_low', sa.Float(), nullable=True),
        sa.Column('value_high', sa.Float(), nullable=True),
        sa.Column('value_point', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('outlook_note', sa.Text(), nullable=True),
        sa.Column('confidence', sa.String(length=32), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('source_chunk', sa.String(length=64), nullable=True),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['doc_id'], ['documents.id'], name='fk_guidance_insights_doc', ondelete='CASCADE'),
    )
    op.create_index('ix_guidance_insights_doc_id', 'guidance_insights', ['doc_id'])
    op.create_index('ix_guidance_insights_created_at', 'guidance_insights', ['created_at'])
    op.create_index('ix_guidance_insights_metric', 'guidance_insights', ['metric'])


def downgrade() -> None:
    op.drop_index('ix_guidance_insights_metric', table_name='guidance_insights')
    op.drop_index('ix_guidance_insights_created_at', table_name='guidance_insights')
    op.drop_index('ix_guidance_insights_doc_id', table_name='guidance_insights')
    op.drop_table('guidance_insights')
