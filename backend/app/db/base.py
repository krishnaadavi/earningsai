import os
import logging
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

def _normalize_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
    return url

engine = None
SessionLocal: Optional[sessionmaker] = None


def init_db() -> None:
    """Initialize SQLAlchemy engine and ensure pgvector extension & tables.
    No-op if DATABASE_URL is not configured.
    """
    global engine, SessionLocal
    if not DATABASE_URL:
        logger.info("db: DATABASE_URL not set; running in in-memory mode (P0)")
        return
    if engine is not None:
        return
    url = _normalize_url(DATABASE_URL)
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    # Ensure pgvector extension exists (Postgres with pgvector installed)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as e:
        logger.warning("db: could not ensure vector extension: %s", e)
    # Import models after engine is ready to avoid circular imports
    from app.db.models import Base  # noqa: WPS433
    Base.metadata.create_all(engine)
    # Best-effort: ensure P1 metadata columns exist on documents table
    try:
        with engine.begin() as conn:
            conn.execute(text(
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
            ))
    except Exception as e:
        logger.warning("db: could not ensure documents extra columns: %s", e)
    logger.info("db: initialized and tables ensured")


@contextmanager
def db_session():
    if SessionLocal is None:
        raise RuntimeError("SessionLocal is not initialized; set DATABASE_URL and restart")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
