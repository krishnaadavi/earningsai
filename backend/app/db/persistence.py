from __future__ import annotations

from typing import List, Tuple, Optional
import uuid
import numpy as np

from app.db.base import db_session
from app.db import base as db_base
from app.db.models import Document, ChunkModel, GuidanceInsight
from app.models.types import Chunk


def is_db_enabled() -> bool:
    # Important: reference SessionLocal on the module to avoid stale binding
    return getattr(db_base, "SessionLocal", None) is not None


def save_document(
    doc_id: str,
    filename: Optional[str],
    chunks: List[Chunk],
    embeddings: np.ndarray,
    *,
    ticker: Optional[str] = None,
    company: Optional[str] = None,
    form_type: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    source_url: Optional[str] = None,
    ingest_status: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Persist document metadata, chunks and embeddings.
    Idempotent for the given doc_id: existing rows will be replaced.
    """
    if not is_db_enabled():
        return
    # Ensure shapes align
    assert embeddings.shape[0] == len(chunks), "embeddings/chunks length mismatch"
    with db_session() as s:
        # Upsert-like behavior: delete existing and insert fresh
        s.query(ChunkModel).filter(ChunkModel.doc_id == doc_id).delete()
        s.query(Document).filter(Document.id == doc_id).delete()
        s.flush()
        s.add(
            Document(
                id=doc_id,
                filename=filename,
                ticker=ticker,
                company=company,
                form_type=form_type,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                source_url=source_url,
                ingest_status=ingest_status,
                error=error,
            )
        )
        # Flush to ensure parent row exists before child inserts (FK dependency)
        s.flush()
        for i, c in enumerate(chunks):
            emb = embeddings[i].tolist()
            s.add(
                ChunkModel(
                    id=c.id or str(uuid.uuid4()),
                    doc_id=doc_id,
                    section=c.section,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    text=c.text,
                    embedding=emb,
                )
            )
        # commit happens in db_session context manager


def load_document(doc_id: str) -> Optional[dict]:
    """Load chunks + embeddings for a document from DB.
    Returns dict with keys: chunks (List[Chunk]), embeddings (np.ndarray)
    or None if not found / DB disabled.
    """
    if not is_db_enabled():
        return None
    with db_session() as s:
        rows = (
            s.query(ChunkModel)
            .filter(ChunkModel.doc_id == doc_id)
            .order_by(ChunkModel.page_start.asc(), ChunkModel.id.asc())
            .all()
        )
        if not rows:
            return None
        chunks: List[Chunk] = []
        embs: List[List[float]] = []
        for r in rows:
            chunks.append(
                Chunk(
                    id=r.id,
                    text=r.text,
                    section=r.section,
                    page_start=r.page_start,
                    page_end=r.page_end,
                )
            )
            # pgvector returns list[float] or memoryview; convert to list
            if isinstance(r.embedding, (list, tuple)):
                embs.append(list(r.embedding))
            else:
                # Fallback: try numpy conversion if needed
                embs.append(np.array(r.embedding).tolist())
        return {"chunks": chunks, "embeddings": np.array(embs, dtype=np.float32)}


def save_guidance_insights(doc_id: str, insights: List[dict]) -> None:
    if not is_db_enabled():
        return
    with db_session() as s:
        s.query(GuidanceInsight).filter(GuidanceInsight.doc_id == doc_id).delete()
        for item in insights or []:
            s.add(
                GuidanceInsight(
                    id=item.get("id") or str(uuid.uuid4()),
                    doc_id=doc_id,
                    metric=item.get("metric"),
                    period=item.get("period"),
                    value_low=item.get("value_low"),
                    value_high=item.get("value_high"),
                    value_point=item.get("value_point"),
                    unit=item.get("unit"),
                    outlook_note=item.get("outlook_note"),
                    confidence=item.get("confidence"),
                    source=item.get("source"),
                    source_chunk=item.get("source_chunk"),
                    citations=item.get("citations"),
                )
            )


def load_guidance_insights(doc_id: str) -> List[dict]:
    if not is_db_enabled():
        return []
    with db_session() as s:
        rows = (
            s.query(GuidanceInsight)
            .filter(GuidanceInsight.doc_id == doc_id)
            .order_by(GuidanceInsight.created_at.desc(), GuidanceInsight.id.asc())
            .all()
        )
        out: List[dict] = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "metric": r.metric,
                    "period": r.period,
                    "value_low": r.value_low,
                    "value_high": r.value_high,
                    "value_point": r.value_point,
                    "unit": r.unit,
                    "outlook_note": r.outlook_note,
                    "confidence": r.confidence,
                    "source": r.source,
                    "source_chunk": r.source_chunk,
                    "citations": r.citations or [],
                }
            )
        return out
