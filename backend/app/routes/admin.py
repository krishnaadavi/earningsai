from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter

from app.db.base import db_session
from app.db.models import EarningsEvent
from app.routes.earnings import earnings_calendar
from app.routes.discovery import ingest_symbol, IngestSymbolRequest

router = APIRouter()


def _week_bounds(d: date) -> tuple[date, date]:
    # Monday..Sunday
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


@router.post("/admin/refresh_week")
async def admin_refresh_week(start: Optional[str] = None, end: Optional[str] = None) -> Dict:
    """Refresh earnings calendar for a week range using providers and return count."""
    if not start or not end:
        s, e = _week_bounds(date.today())
        start = s.isoformat()
        end = e.isoformat()
    # Reuse earnings endpoint logic with refresh=1
    rows = await earnings_calendar(start=start, end=end, refresh="1")
    return {"start": start, "end": end, "count": len(rows)}


@router.post("/admin/ingest_today")
async def admin_ingest_today(limit: int = 50, batch: int = 6) -> Dict:
    """Ingest press release/transcript PDFs for today's earnings tickers.
    Returns summary counts and per-ticker status.
    """
    today = date.today()
    # Load today's tickers from DB (extract plain strings inside the session)
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
        return {"date": today.isoformat(), "requested": 0, "success": 0, "errors": []}

    tickers = tickers[: max(1, min(limit, len(tickers)))]

    # Concurrency limiter
    sem = asyncio.Semaphore(max(1, min(batch, 10)))

    results: List[Dict] = []

    async def _run_one(t: str):
        async with sem:
            try:
                resp = await ingest_symbol(IngestSymbolRequest(ticker=t))
                results.append({"ticker": t, "ok": True, "doc_id": getattr(resp, "doc_id", None) or getattr(resp, "doc_id", None)})
            except Exception as e:
                results.append({"ticker": t, "ok": False, "error": str(e)})

    await asyncio.gather(*[_run_one(t) for t in tickers])

    ok = sum(1 for r in results if r.get("ok"))
    errs = [r for r in results if not r.get("ok")]
    return {
        "date": today.isoformat(),
        "requested": len(tickers),
        "success": ok,
        "errors": errs,
        "items": results,
    }
