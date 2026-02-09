"""add document metadata columns

Revision ID: 20250911_add_document_metadata
Revises: 
Create Date: 2025-09-11 19:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250911_add_document_metadata'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension exists (Postgres)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Add columns to documents table if not already present
    op.execute(
        """
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS ticker VARCHAR(32),
            ADD COLUMN IF NOT EXISTS company VARCHAR(255),
            ADD COLUMN IF NOT EXISTS form_type VARCHAR(32),
            ADD COLUMN IF NOT EXISTS fiscal_year INTEGER,
            ADD COLUMN IF NOT EXISTS fiscal_period VARCHAR(16),
            ADD COLUMN IF NOT EXISTS source_url TEXT,
            ADD COLUMN IF NOT EXISTS ingest_status VARCHAR(32),
            ADD COLUMN IF NOT EXISTS error TEXT
        """
    )


def downgrade() -> None:
    # Downgrade is optional and may drop metadata columns if present
    op.execute(
        """
        ALTER TABLE documents
            DROP COLUMN IF EXISTS error,
            DROP COLUMN IF EXISTS ingest_status,
            DROP COLUMN IF EXISTS source_url,
            DROP COLUMN IF EXISTS fiscal_period,
            DROP COLUMN IF EXISTS fiscal_year,
            DROP COLUMN IF EXISTS form_type,
            DROP COLUMN IF EXISTS company,
            DROP COLUMN IF EXISTS ticker
        """
    )
