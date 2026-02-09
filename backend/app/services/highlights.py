from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from app.db.base import db_session
from app.db.models import Highlight, EarningsEvent
from app.models.types import Chunk
from app.services.metric_extractors import (
    extract_core_metrics,
    extract_series_for_metrics,
    extract_guidance,
    extract_buybacks,
)


def _bullets_from_metrics(metrics: Dict[str, Dict]) -> List[str]:
    out: List[str] = []
    if "revenue" in metrics:
        v = metrics["revenue"]["value"]
        out.append(f"Revenue: ${v:,.0f}M")
    if "eps_nongaap" in metrics:
        out.append(f"EPS (non-GAAP): ${metrics['eps_nongaap']['value']:.2f}")
    elif "eps_gaap" in metrics:
        out.append(f"EPS (GAAP): ${metrics['eps_gaap']['value']:.2f}")
    if "gross_margin" in metrics:
        out.append(f"Gross margin: {metrics['gross_margin']['value']:.1f}%")
    if "fcf" in metrics:
        out.append(f"FCF: ${metrics['fcf']['value']:,.0f}M")
    return out[:3]


def _score_from_summary(metrics: Dict[str, Dict], guidance: Dict) -> float:
    score = 0.0
    score += len(metrics) * 0.5
    if guidance.get("guidance"):
        score += 1.0
    return score


def create_highlight_and_event(
    ticker: str,
    company: Optional[str],
    doc_id: str,
    chunks: List[Chunk],
) -> Optional[str]:
    """Compute a basic highlight summary and persist it, and ensure an earnings event for today.
    Returns the created highlight id, or None on failure.
    """
    try:
        metrics = extract_core_metrics(chunks)
        guidance = extract_guidance(chunks)
        # Simple series for charts if needed later
        # series = extract_series_for_metrics(chunks, ["revenue", "eps_gaap", "eps_nongaap"])  # not stored yet
        bullets = _bullets_from_metrics(metrics)
        sent_summary: Dict = {
            "metrics": metrics,
            "guidance": guidance.get("guidance", []),
            "bullets": bullets,
            # placeholders for future deltas/guidance direction/sentiment
            "deltas": {},
            "sentiment": None,
        }
        hid = str(uuid.uuid4())
        with db_session() as s:
            # Upsert-like: just insert a new highlight; duplicates are okay for now
            s.add(
                Highlight(
                    id=hid,
                    ticker=ticker.upper(),
                    doc_id=doc_id,
                    summary_json=sent_summary,
                    rank_score=_score_from_summary(metrics, {"guidance": guidance.get("guidance")}),
                )
            )
            # Ensure an event exists for today (UTC date)
            today = date.today()
            existing = (
                s.query(EarningsEvent)
                .filter(EarningsEvent.ticker == ticker.upper(), EarningsEvent.event_date == today)
                .first()
            )
            if not existing:
                s.add(
                    EarningsEvent(
                        id=str(uuid.uuid4()),
                        ticker=ticker.upper(),
                        company=company,
                        event_date=today,
                        time_of_day=None,
                        status="reported",
                        source="ingest_symbol",
                    )
                )
        return hid
    except Exception:
        # Swallow errors to avoid breaking ingest flow
        return None
