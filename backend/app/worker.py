from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, List

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

# Load env early (Heroku uses config vars; this is harmless locally)
load_dotenv()

from app.db.base import init_db, db_session
from app.db.models import EarningsEvent
from app.routes.earnings import earnings_calendar
from app.routes.discovery import ingest_symbol, IngestSymbolRequest

log = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO)


async def job_refresh_next_14_days() -> None:
    """Backfill the next two weeks of earnings calendar from providers."""
    today = date.today()
    start = today
    end = today + timedelta(days=13)
    try:
        rows = await earnings_calendar(start=start.isoformat(), end=end.isoformat(), refresh="1")
        log.info("calendar refresh ok: %s..%s -> %d rows", start, end, len(rows) if isinstance(rows, list) else -1)
    except Exception as e:
        log.exception("calendar refresh failed: %s", e)


async def job_ingest_today(batch: int = 6, limit: int = 100) -> Dict:
    """Ingest PDFs for today's earnings tickers.
    Mirrors /api/admin/ingest_today but runs as a background job.
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
        tickers: List[str] = []
        seen: set[str] = set()
        for (tk,) in rows:
            t = (tk or "").upper()
            if t and t not in seen:
                seen.add(t)
                tickers.append(t)

    if not tickers:
        log.info("ingest_today: no tickers for %s", today)
        return {"date": today.isoformat(), "requested": 0, "success": 0, "errors": []}

    tickers = tickers[: max(1, min(limit, len(tickers)))]

    sem = asyncio.Semaphore(max(1, min(batch, 10)))
    results: List[Dict] = []

    async def _run_one(t: str):
        async with sem:
            try:
                resp = await ingest_symbol(IngestSymbolRequest(ticker=t))
                results.append({"ticker": t, "ok": True, "doc_id": getattr(resp, "doc_id", None)})
            except Exception as e:
                results.append({"ticker": t, "ok": False, "error": str(e)})

    await asyncio.gather(*[_run_one(t) for t in tickers])

    ok = sum(1 for r in results if r.get("ok"))
    errs = [r for r in results if not r.get("ok")]
    log.info("ingest_today: %d/%d ok (errors=%d)", ok, len(tickers), len(errs))
    return {
        "date": today.isoformat(),
        "requested": len(tickers),
        "success": ok,
        "errors": errs,
        "items": results,
    }


async def main() -> None:
    init_db()
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))

    # Daily calendar refresh
    scheduler.add_job(job_refresh_next_14_days, "cron", hour=5, minute=10)  # 05:10 UTC daily

    # Ingest today, every 15 minutes
    scheduler.add_job(job_ingest_today, "cron", minute="*/15")

    scheduler.start()

    # Run once on startup to warm things up
    await job_refresh_next_14_days()
    await job_ingest_today()

    # Keep process alive
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
