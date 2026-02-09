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
from datetime import date, timedelta
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

    # If no document context, route certain generic queries to API-backed endpoints
    doc_id = (req.doc_id or "").strip() if isinstance(req.doc_id, str) else ""
    if not doc_id:
        ql = (req.question or "").lower()
        try:
            # Today's daily highlights
            if ("highlight" in ql and "today" in ql) or ("daily highlights" in ql):
                from app.routes.earnings import highlights_today  # local import to avoid circulars
                items = await highlights_today(limit=8)
                bullets = []
                for it in items[:8]:
                    # Try to surface the first summary bullet if available
                    summ = (it.summary or {}) if hasattr(it, 'summary') else {}
                    text = None
                    try:
                        arr = summ.get('bullets') or []
                        text = arr[0] if arr else None
                    except Exception:
                        text = None
                    label = f"{it.ticker}{' · ' + it.company if it.company else ''}"
                    bullets.append(AnswerBullet(text=(text or label), citations=[]))
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})

            # This week's highlights
            if ("highlight" in ql and ("this week" in ql or "weekly" in ql)):
                from app.routes.earnings import highlights_this_week
                items = await highlights_this_week(limit=10)
                bullets = []
                for it in items[:10]:
                    summ = (it.summary or {}) if hasattr(it, 'summary') else {}
                    text = None
                    try:
                        arr = summ.get('bullets') or []
                        text = arr[0] if arr else None
                    except Exception:
                        text = None
                    label = f"{it.ticker}{' · ' + it.company if it.company else ''}"
                    bullets.append(AnswerBullet(text=(text or label), citations=[]))
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})

            # Most important earnings today -> list today's calendar
            if ("most" in ql and "earnings" in ql and "today" in ql) or ("today" in ql and "earnings" in ql):
                from app.routes.earnings import earnings_calendar
                today = date.today().isoformat()
                events = await earnings_calendar(start=today, end=today, refresh=None)
                bullets = [
                    AnswerBullet(
                        text=f"{ev.ticker}{' · ' + ev.company if ev.company else ''}{' · ' + (ev.time_of_day or 'TBD')}",
                        citations=[],
                    ) for ev in (events or [])
                ][:10]
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})

            # Today's earnings summaries (EPS surprises)
            if ("today" in ql and ("summary" in ql or "summaries" in ql or "eps" in ql)):
                from app.routes.earnings import earnings_summaries_today
                try:
                    summaries = await earnings_summaries_today(limit=12, per_ticker=4)
                except Exception:
                    summaries = []
                bullets = []
                for s in (summaries or [])[:12]:
                    try:
                        t = getattr(s, 'ticker', None) or (s.get('ticker') if isinstance(s, dict) else None)
                        comp = getattr(s, 'company', None) if hasattr(s, 'company') else (s.get('company') if isinstance(s, dict) else None)
                        latest = getattr(s, 'latest', None) if hasattr(s, 'latest') else (s.get('latest') if isinstance(s, dict) else None)
                        if not t:
                            continue
                        label_parts = [(t or '').upper()]
                        if comp:
                            label_parts.append(comp)
                        # format latest EPS surprise if present
                        if isinstance(latest, dict):
                            per = latest.get('period') or ''
                            rep = latest.get('reported_eps')
                            est = latest.get('estimated_eps')
                            spr = latest.get('surprise')
                            spr_pct = latest.get('surprise_pct')
                            def fmt_eps(x):
                                try:
                                    return f"{float(x):.2f}"
                                except Exception:
                                    return None
                            rep_s = fmt_eps(rep)
                            est_s = fmt_eps(est)
                            spr_s = fmt_eps(spr)
                            sprp_s = None
                            try:
                                sprp_s = f"{float(spr_pct):.1f}%" if spr_pct is not None else None
                            except Exception:
                                sprp_s = None
                            details = []
                            if rep_s is not None:
                                details.append(f"EPS {rep_s}")
                            if est_s is not None:
                                details.append(f"vs est {est_s}")
                            if spr_s is not None or sprp_s is not None:
                                sp = ("+" if (spr or 0) > 0 else "") + (spr_s or "")
                                if sprp_s:
                                    sp = (sp + (f" ({sprp_s})" if sp else sprp_s)).strip()
                                if sp:
                                    details.append(f"surprise {sp}")
                            if per:
                                details.append(per)
                            txt = " · ".join(label_parts + details) if details else " · ".join(label_parts)
                        else:
                            txt = " · ".join(label_parts + ["no EPS data"]) 
                        bullets.append(AnswerBullet(text=txt, citations=[]))
                    except Exception:
                        continue
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})

            # This week's earnings (calendar) instead of highlights
            if (("this week" in ql or "weekly" in ql) and "earnings" in ql) or ("week" in ql and "earnings" in ql):
                from app.routes.earnings import earnings_calendar
                today = date.today()
                start = today - timedelta(days=today.weekday())  # Monday
                end = start + timedelta(days=6)  # Sunday
                events = await earnings_calendar(start=start.isoformat(), end=end.isoformat(), refresh=None)
                bullets = [
                    AnswerBullet(
                        text=f"{ev.ticker}{' · ' + ev.company if ev.company else ''} · {ev.event_date.split('T')[0]}{' · ' + (ev.time_of_day or 'TBD')}",
                        citations=[],
                    ) for ev in (events or [])
                ][:15]
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})

            # Pre-market movers (uses Finnhub; inferred tickers)
            if ("pre-market" in ql and "mover" in ql) or ("pre market" in ql and "mover" in ql):
                from app.routes.market import market_movers
                movers = await market_movers(limit=10)
                fmt = lambda p: (f"up {abs(p):.2f}%" if (p or 0) >= 0 else f"down {abs(p):.2f}%")
                bullets = [
                    AnswerBullet(
                        text=f"{m.ticker}: {fmt(m.change_percent or 0.0)}",
                        citations=[],
                    ) for m in (movers or [])
                ][:10]
                if bullets:
                    return QueryResponse(bullets=bullets, chart={})
        except Exception:
            # Fall through to generic insufficient-context response
            pass
        return QueryResponse(
            bullets=[AnswerBullet(text="No context set. Try: 'Show me today's daily highlights' or set a doc_id context.", citations=[])],
            chart={},
        )

    # Document-specific QA path
    doc = store.documents.get(doc_id)
    if not doc and is_db_enabled():
        try:
            loaded = load_document(doc_id)
            if loaded:
                doc = loaded
                # Optional: warm in-memory cache
                store.documents[doc_id] = loaded
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
    logger.info("query: doc_id=%s q=%r variants=%d top_sims=%s", doc_id, req.question, len(variants), [round(s,3) for _, s in top[:5]])

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
