from __future__ import annotations

import asyncio
import uuid
from datetime import date
import logging
from typing import Dict, List

from fastapi import APIRouter

from app.db.base import db_session
from app.db.models import EarningsEvent, IngestionRun
from app.db.persistence import is_db_enabled
from app.routes.discovery import ingest_symbol, IngestSymbolRequest
from app.services.metrics import begin_run, end_run

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/admin/ingest_today")
async def admin_ingest_today(limit: int = 50, batch: int = 6, prefer: str | None = None) -> Dict:
    """Manually ingest today's earnings PDFs (press releases/transcripts).
    Mirrors the worker job but exposed as an admin endpoint for testing.
    """
    today = date.today()
    # Collect tickers within session; return only plain strings
    with db_session() as s:
        rows: List[tuple] = (
            s.query(EarningsEvent.ticker)
            .filter(EarningsEvent.event_date == today)
            .order_by(EarningsEvent.ticker.asc())
            .all()
        )
        seen: set[str] = set()
        tickers: List[str] = []
        for (tk,) in rows:
            t = (tk or "").upper()
            if t and t not in seen:
                seen.add(t)
                tickers.append(t)

    if not tickers:
        return {"date": today.isoformat(), "requested": 0, "success": 0, "errors": [], "items": [], "tickers": []}

    tickers = tickers[: max(1, min(int(limit), len(tickers)))]

    sem = asyncio.Semaphore(max(1, min(int(batch), 10)))
    results: List[Dict] = []

    begin_run()

    async def _run_one(t: str):
        async with sem:
            try:
                resp = await ingest_symbol(IngestSymbolRequest(ticker=t, prefer=prefer))
                results.append({"ticker": t, "ok": True, "doc_id": getattr(resp, "doc_id", None)})
            except Exception as e:
                results.append({"ticker": t, "ok": False, "error": str(e)})

    await asyncio.gather(*[_run_one(t) for t in tickers])

    ok = sum(1 for r in results if r.get("ok"))
    errs = [r for r in results if not r.get("ok")]
    summary = {
        "date": today.isoformat(),
        "requested": len(tickers),
        "success": ok,
        "errors": errs,
        "items": results,
        "tickers": tickers,
    }

    metrics = end_run()
    summary["metrics"] = metrics

    if is_db_enabled():
        try:
            with db_session() as s:
                s.add(
                    IngestionRun(
                        id=str(uuid.uuid4()),
                        job_type="ingest_today",
                        requested=len(tickers),
                        success=ok,
                        error_count=len(errs),
                        data=summary,
                    )
                )
        except Exception as e:
            # Avoid failing the endpoint if DB commit fails (e.g., disk quota reached)
            try:
                log.warning("admin_ingest_today: failed to persist IngestionRun: %s", e)
            except Exception:
                pass

    return summary
