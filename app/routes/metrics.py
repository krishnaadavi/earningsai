from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.models.types import (
    DocRequest,
    SeriesRequest,
    MetricsResponse,
    SeriesResponse,
    GuidanceResponse,
    BuybacksResponse,
)
from app.memory import store
from app.db.persistence import load_document, is_db_enabled
from app.db.base import db_session
from app.db.models import IngestionRun
from app.services.metric_extractors import (
    extract_core_metrics,
    extract_series_for_metrics,
    extract_guidance,
    extract_buybacks,
)

router = APIRouter()


def _get_doc_or_404(doc_id: str):
    doc = store.documents.get(doc_id)
    if not doc and is_db_enabled():
        try:
            loaded = load_document(doc_id)
            if loaded:
                doc = loaded
                store.documents[doc_id] = loaded
        except Exception:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown doc_id")
    return doc


@router.post("/metrics", response_model=MetricsResponse)
async def metrics(req: DocRequest):
    doc = _get_doc_or_404(req.doc_id)
    chunks = doc["chunks"]
    # For P1, run extractors across all chunks (heuristics are lightweight)
    metrics = extract_core_metrics(chunks)
    return {"metrics": metrics}


@router.post("/series", response_model=SeriesResponse)
async def series(req: SeriesRequest):
    doc = _get_doc_or_404(req.doc_id)
    chunks = doc["chunks"]
    series = extract_series_for_metrics(chunks, req.metrics)
    return {"series": series}


@router.post("/guidance", response_model=GuidanceResponse)
async def guidance(req: DocRequest):
    doc = _get_doc_or_404(req.doc_id)
    chunks = doc["chunks"]
    data = extract_guidance(chunks)
    return {"guidance": data}


@router.post("/buybacks", response_model=BuybacksResponse)
async def buybacks(req: DocRequest):
    doc = _get_doc_or_404(req.doc_id)
    chunks = doc["chunks"]
    data = extract_buybacks(chunks)
    return {"buybacks": data}


# Ingestion metrics
def _normalize_run(r: IngestionRun) -> Dict[str, Any]:
    d = {
        "id": r.id,
        "job_type": r.job_type,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "requested": r.requested,
        "success": r.success,
        "error_count": r.error_count,
    }
    if isinstance(r.data, dict):
        d["data"] = r.data
        # convenient top-level aliases for UI
        if r.job_type == "ingest_today":
            d["tickers"] = r.data.get("tickers") or []
        if r.job_type == "refresh_next_14_days":
            d["count"] = r.data.get("count")
            d["range"] = {"start": r.data.get("start"), "end": r.data.get("end")}
    return d


@router.get("/metrics/ingestion/last")
async def last_ingestion_runs() -> Dict[str, Any]:
    if not is_db_enabled():
        return {"enabled": False}
    with db_session() as s:
        last_ingest = (
            s.query(IngestionRun)
            .filter(IngestionRun.job_type == "ingest_today")
            .order_by(IngestionRun.created_at.desc())
            .first()
        )
        last_refresh = (
            s.query(IngestionRun)
            .filter(IngestionRun.job_type == "refresh_next_14_days")
            .order_by(IngestionRun.created_at.desc())
            .first()
        )
        # Normalize while session is open to avoid DetachedInstanceError
        norm_ingest = _normalize_run(last_ingest) if last_ingest else None
        norm_refresh = _normalize_run(last_refresh) if last_refresh else None
    return {
        "enabled": True,
        "last_ingest": norm_ingest,
        "last_refresh": norm_refresh,
    }


@router.get("/metrics/ingestion/recent")
async def recent_ingestion_runs(limit: int = 25) -> Dict[str, Any]:
    if not is_db_enabled():
        return {"enabled": False, "items": []}
    limit = max(1, min(100, int(limit)))
    with db_session() as s:
        rows = (
            s.query(IngestionRun)
            .order_by(IngestionRun.created_at.desc())
            .limit(limit)
            .all()
        )
        items = [_normalize_run(r) for r in rows]
    return {
        "enabled": True,
        "items": items,
    }
