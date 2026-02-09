from __future__ import annotations

import os
from typing import List
from fastapi import APIRouter, HTTPException

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
from app.services.guidance_enricher import get_guidance, enrich_guidance_for_doc
from app.services.metric_extractors import (
    extract_core_metrics,
    extract_series_for_metrics,
    extract_guidance,
    extract_buybacks,
)

router = APIRouter()

def _check_and_increment_budget() -> None:
    """Simple per-process budget guard for guidance rebuilds.
    If BUDGET_MAX_QUERIES is set to a positive integer, enforce a cap
    on total rebuild calls in this process lifetime.
    """
    try:
        cap = int(os.getenv("BUDGET_MAX_QUERIES", "0") or "0")
    except Exception:
        cap = 0
    if cap <= 0:
        return
    used = int(store.budget.get("queries", 0) or 0)
    if used >= cap:
        raise HTTPException(status_code=429, detail="Budget exceeded for guidance rebuilds")
    store.budget["queries"] = used + 1


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
    entries = await get_guidance(req.doc_id)
    if entries:
        return {"guidance": entries}
    # Fallback to heuristic for empty result
    doc = _get_doc_or_404(req.doc_id)
    data = extract_guidance(doc["chunks"])
    return {"guidance": data.get("guidance") if isinstance(data, dict) else data}


@router.get("/guidance/{doc_id}", response_model=GuidanceResponse)
async def guidance_cached(doc_id: str):
    """Return cached guidance if available; try DB; otherwise empty list.
    Does not force LLM or re-enrichment.
    """
    cached = store.guidance.get(doc_id)
    if cached:
        return {"guidance": cached}
    if is_db_enabled():
        try:
            from app.db.persistence import load_guidance_insights

            rows = load_guidance_insights(doc_id)
            if rows:
                store.guidance[doc_id] = rows
                return {"guidance": rows}
        except Exception:
            pass
    # If doc exists in memory, provide heuristic-only fallback to be helpful
    doc = store.documents.get(doc_id)
    if doc:
        data = extract_guidance(doc.get("chunks") or [])
        return {"guidance": data.get("guidance") if isinstance(data, dict) else data}
    # Otherwise return empty list (no 404 to make it easy for clients)
    return {"guidance": []}


@router.post("/buybacks", response_model=BuybacksResponse)
async def buybacks(req: DocRequest):
    doc = _get_doc_or_404(req.doc_id)
    chunks = doc["chunks"]
    data = extract_buybacks(chunks)
    # extractor returns {"buybacks": [...]}; response expects a list
    items = data.get("buybacks") if isinstance(data, dict) else data
    return {"buybacks": items}


@router.post("/guidance/rebuild", response_model=GuidanceResponse)
async def guidance_rebuild(req: DocRequest):
    """Force re-enrichment for guidance and return normalized entries."""
    _check_and_increment_budget()
    entries = await enrich_guidance_for_doc(req.doc_id, force=True)
    return {"guidance": entries}
