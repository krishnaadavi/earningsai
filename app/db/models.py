from __future__ import annotations

from sqlalchemy import DateTime, Date, ForeignKey, Integer, String, Text, Float, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # P1 metadata
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingest_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    requested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # e.g., {"requested": [...], "ok": [...], "errors": [...]} 


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    section: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Vector] = mapped_column(Vector(1536))


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[Date] = mapped_column(Date, index=True)
    time_of_day: Mapped[str | None] = mapped_column(String(8), nullable=True)  # BMO/AMC
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # upcoming/reported
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Highlight(Base):
    __tablename__ = "highlights"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    doc_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
