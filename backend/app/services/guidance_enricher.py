from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Dict, Any, List, Optional

from app.models.types import Chunk
from app.services.metric_extractors import extract_guidance as heuristic_extract_guidance
from app.services.guidance_llm import (
    generate_guidance_entries,
    attach_citations,
)
from app.memory import store
from app.db.persistence import (
    is_db_enabled,
    load_document,
    save_guidance_insights,
    load_guidance_insights,
)

logger = logging.getLogger(__name__)
GUIDANCE_MAX_CHUNKS = int(os.getenv("GUIDANCE_MAX_CHUNKS", "12") or "12")

_GUIDANCE_KEYWORDS = ["guidance", "outlook", "expects", "forecast", "target", "range"]


def _select_candidate_chunks(chunks: List[Chunk], limit: int = GUIDANCE_MAX_CHUNKS) -> List[Chunk]:
    selected: List[Chunk] = []
    for chunk in chunks:
        if len(selected) >= limit:
            break
        text = chunk.text.lower()
        if any(keyword in text for keyword in _GUIDANCE_KEYWORDS):
            selected.append(chunk)
    if not selected:
        selected = chunks[:limit]
    return selected


def _heuristic_fallback(chunks: List[Chunk]) -> List[Dict[str, Any]]:
    data = heuristic_extract_guidance(chunks)
    guidance_items = (data or {}).get("guidance") or []
    normalized: List[Dict[str, Any]] = []
    for item in guidance_items:
        rng = item.get("range") or []
        value_low = None
        value_high = None
        value_point = item.get("value")
        if len(rng) == 1:
            value_point = rng[0]
        elif len(rng) >= 2:
            value_low = rng[0]
            value_high = rng[1]
        normalized.append(
            {
                "id": str(uuid.uuid4()),
                "metric": item.get("type"),
                "period": item.get("period"),
                "value_low": value_low,
                "value_high": value_high,
                "value_point": value_point,
                "unit": item.get("unit"),
                "outlook_note": None,
                "confidence": "low",
                "source": "heuristic",
                "source_chunk": None,
                "citations": [c.dict() for c in item.get("citations", [])],
            }
        )
    return normalized


def _chunk_label_map(chunks: List[Chunk]) -> Dict[str, Chunk]:
    return {f"C{idx + 1}": chunk for idx, chunk in enumerate(chunks)}


async def _run_llm(chunks: List[Chunk], meta: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunk_map = _chunk_label_map(chunks)

    def _call_llm() -> List[Dict[str, Any]]:
        entries = generate_guidance_entries(chunks, meta=meta)
        if not entries:
            return []
        enriched = attach_citations(entries, chunk_map)
        results: List[Dict[str, Any]] = []
        for entry in enriched:
            data = {**entry}
            data.pop("chunk_id", None)
            data.setdefault("id", str(uuid.uuid4()))
            data.setdefault("source", "openai")
            data.setdefault("source_chunk", entry.get("chunk_id"))
            results.append(data)
        return results

    try:
        return await asyncio.to_thread(_call_llm)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("guidance_llm call failed: %s", exc)
        return []


async def enrich_guidance_for_doc(
    doc_id: str,
    *,
    doc: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> List[Dict[str, Any]]:
    if not doc:
        doc = store.documents.get(doc_id)
        if not doc and is_db_enabled():
            loaded = load_document(doc_id)
            if loaded:
                doc = loaded
    if not doc:
        logger.info("enrich_guidance_for_doc: doc %s not found", doc_id)
        return []

    if not force:
        cached = store.guidance.get(doc_id)
        if cached:
            return cached
        db_cached = load_guidance_insights(doc_id)
        if db_cached:
            store.guidance[doc_id] = db_cached
            return db_cached

    chunks: List[Chunk] = doc.get("chunks") or []
    if not chunks:
        return []

    meta = doc.get("meta") or {}
    candidates = _select_candidate_chunks(chunks)

    entries: List[Dict[str, Any]] = []
    if os.getenv("OPENAI_API_KEY"):
        entries = await _run_llm(candidates, meta)

    if not entries:
        entries = _heuristic_fallback(candidates)

    store.guidance[doc_id] = entries
    if is_db_enabled():
        save_guidance_insights(doc_id, entries)
    return entries


async def get_guidance(doc_id: str) -> List[Dict[str, Any]]:
    cached = store.guidance.get(doc_id)
    if cached:
        return cached
    return await enrich_guidance_for_doc(doc_id)
