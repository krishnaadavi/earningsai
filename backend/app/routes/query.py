from fastapi import APIRouter, HTTPException
from app.models.types import QueryRequest, QueryResponse, AnswerBullet, Citation
from app.services.embedder import embed_texts
from app.services.retriever import build_index
from app.services.qa import answer_question
from app.services.trend_extractor import extract_series
from app.memory import store
from app.services.budget_guard import check_and_increment_query_budget
from app.db.persistence import load_document, is_db_enabled
from app.services.metric_extractors import extract_core_metrics
import numpy as np
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _expand_query(q: str) -> list:
    ql = q.lower()
    variants = [q.strip()]
    # FCF synonyms
    if "fcf" in ql or "free cash flow" in ql:
        variants += [
            "free cash flow growth",
            "free cash flow guidance",
            "free cash flow outlook",
            "cash flow from operations minus capital expenditures",
        ]
    # Guidance/outlook synonyms
    if any(w in ql for w in ["guidance", "projection", "projections", "forecast", "outlook"]):
        variants += [
            "guidance next year",
            "outlook next fiscal year",
            "forecast FY next year",
        ]
    # CFO / CAPEX terminology for deriving FCF
    if any(w in ql for w in ["fcf", "free cash flow", "cash flow"]):
        variants += [
            "operating cash flow",
            "cash provided by operating activities",
            "capital expenditures",
            "capex",
            "purchases of property and equipment",
        ]
    # Generic growth phrasing
    if "growth" in ql:
        variants += [
            "year-over-year growth",
            "yoy growth",
        ]
    # De-duplicate while preserving order
    seen = set()
    out = []
    for v in variants:
        if v and v not in seen:
            out.append(v)
            seen.add(v)
    return out[:6]

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    # Enforce simple per-process query cap
    check_and_increment_query_budget()
    doc = store.documents.get(req.doc_id)
    if not doc and is_db_enabled():
        try:
            loaded = load_document(req.doc_id)
            if loaded:
                doc = loaded
                # Optional: warm in-memory cache
                store.documents[req.doc_id] = loaded
        except Exception:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Unknown doc_id")

    chunks = doc["chunks"]
    embs = doc["embeddings"]  # (N,D)

    # Expand query with simple domain synonyms to improve recall
    variants = _expand_query(req.question)
    qvecs = embed_texts(variants)  # (V,D)
    # build ad-hoc index and search per variant
    from app.services.retriever import Index
    index = Index(embeddings=embs, chunks=chunks)
    agg: dict = {}  # chunk_id -> (chunk, max_sim)
    for i in range(qvecs.shape[0]):
        topv = index.search(qvecs[i], top_k=6)
        for c, s in topv:
            prev = agg.get(c.id)
            if not prev or s > prev[1]:
                agg[c.id] = (c, float(s))
    # sort by similarity desc and take top
    top = sorted(agg.values(), key=lambda x: -x[1])[:8]
    logger.info("query: doc_id=%s q=%r variants=%d top_sims=%s", req.doc_id, req.question, len(variants), [round(s,3) for _, s in top[:5]])

    # If absolutely nothing retrieved, return insufficient context
    if not top:
        return QueryResponse(
            bullets=[AnswerBullet(text="Insufficient context.", citations=[])],
            chart={}
        )

    # Include adjacent chunks to improve continuity
    id_to_index = {c.id: i for i, c in enumerate(chunks)}
    selected_ids = []
    top_chunks = []
    for c, _ in top:
        idx = id_to_index.get(c.id)
        for j in [idx - 1, idx, idx + 1]:
            if j is None or j < 0 or j >= len(chunks):
                continue
            cid = chunks[j].id
            if cid not in selected_ids:
                selected_ids.append(cid)
                top_chunks.append(chunks[j])
            if len(top_chunks) >= 10:
                break
        if len(top_chunks) >= 10:
            break
    try:
        logger.info(
            "query: top_chunks pages=%s sections=%s",
            [f"{c.page_start}-{c.page_end}" for c in top_chunks[:5]],
            [c.section for c in top_chunks[:5]],
        )
    except Exception:
        pass
    # Metrics-first routing: detect metric-intent questions and answer via extractors with citations
    ql = req.question.lower()
    metric_intent = any(w in ql for w in [
        "revenue", "gross margin", "operating margin", "eps", "earnings per share",
        "cfo", "operating cash flow", "capex", "capital expenditures", "free cash flow", "fcf",
        "guidance", "outlook", "forecast", "buyback", "repurchase"
    ])

    bullets: list[AnswerBullet] = []
    if metric_intent:
        m = extract_core_metrics(top_chunks)
        if m:
            # Build concise bullets for found metrics (limit to 5)
            for name, item in list(m.items())[:5]:
                value = item.get("value")
                unit = item.get("unit")
                period = item.get("period")
                cits = item.get("citations") or []
                # Ensure citations are of type Citation
                citations = []
                for c in cits:
                    if isinstance(c, Citation):
                        citations.append(c)
                    else:
                        try:
                            citations.append(Citation(**c))
                        except Exception:
                            pass
                txt = f"{name.replace('_', ' ').title()}: {value} {unit or ''}"
                if period:
                    txt += f" ({period})"
                bullets.append(AnswerBullet(text=txt.strip(), citations=citations or []))
        # If nothing extracted, fall through to QA
    if not bullets:
        bullets = answer_question(req.question, top_chunks)

    # If model says insufficient, return explicit insufficient context
    if not bullets:
        return QueryResponse(
            bullets=[AnswerBullet(text="Insufficient context.", citations=[])],
            chart={}
        )

    chart = extract_series(top_chunks)
    return QueryResponse(bullets=bullets, chart=chart)
