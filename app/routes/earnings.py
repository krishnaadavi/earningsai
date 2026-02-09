from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from datetime import date, datetime, timedelta
from sqlalchemy import and_, func
import os
import uuid

from app.db.base import db_session
from app.db.models import EarningsEvent, Highlight
from app.db.persistence import is_db_enabled
from app.services.providers.fmp import fetch_earnings_calendar as fetch_earnings_calendar_fmp
from app.services.providers.finnhub import (
    fetch_earnings_calendar as fetch_earnings_calendar_finnhub,
    fetch_eps_surprises as finnhub_eps,
)
from app.services.providers.alpha_vantage import fetch_quarterly_earnings as av_eps

router = APIRouter()


# ---------- Response Models ----------
class EarningsEventOut(BaseModel):
    id: str
    ticker: str
    company: Optional[str] = None
    event_date: str
    time_of_day: Optional[str] = None
    status: Optional[str] = None


class HighlightOut(BaseModel):
    id: str
    ticker: str
    company: Optional[str] = None
    summary: dict
    rank_score: Optional[float] = None
    created_at: str


class EPSSurpriseItem(BaseModel):
    period: str
    reported_eps: Optional[float] = None
    estimated_eps: Optional[float] = None
    surprise: Optional[float] = None
    surprise_pct: Optional[float] = None
    provider: Optional[str] = None


class EarningsSummaryOut(BaseModel):
    ticker: str
    company: Optional[str] = None
    latest: Optional[EPSSurpriseItem] = None
    eps: List[EPSSurpriseItem] = []
    sources: List[str] = []


# ---------- Helpers ----------
def _iso(d: date | datetime | None) -> str:
    if not d:
        return ""
    if isinstance(d, datetime):
        return d.isoformat()
    return datetime(d.year, d.month, d.day).isoformat()


def _pick_latest(items: List[dict]) -> Optional[dict]:
    if not items:
        return None
    # items may already be most-recent first; sort defensively by period desc
    def key_fn(it):
        return (it.get("period") or "")
    try:
        items_sorted = sorted(items, key=key_fn, reverse=True)
    except Exception:
        items_sorted = items
    return items_sorted[0] if items_sorted else None


# ---------- Endpoints ----------
@router.get("/earnings/calendar", response_model=List[EarningsEventOut])
async def earnings_calendar(start: Optional[str] = None, end: Optional[str] = None, refresh: Optional[str] = None) -> List[EarningsEventOut]:
    # Fallback curated sample if DB disabled
    if not is_db_enabled():
        today = date.today()
        sample = [
            EarningsEventOut(id=str(uuid.uuid4()), ticker="AAPL", company="Apple Inc.", event_date=_iso(today), time_of_day="BMO", status="reported"),
            EarningsEventOut(id=str(uuid.uuid4()), ticker="MSFT", company="Microsoft Corp.", event_date=_iso(today + timedelta(days=1)), time_of_day="AMC", status="upcoming"),
        ]
        return sample

    # Parse dates
    try:
        start_d = date.fromisoformat(start) if start else date.today() - timedelta(days=3)
        end_d = date.fromisoformat(end) if end else date.today() + timedelta(days=7)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD")

    with db_session() as s:
        q = s.query(EarningsEvent).filter(
            and_(EarningsEvent.event_date >= start_d, EarningsEvent.event_date <= end_d)
        ).order_by(EarningsEvent.event_date.asc(), EarningsEvent.ticker.asc())
        rows: List[EarningsEvent] = q.all()

        need_refresh = False
        if refresh and refresh.strip().lower() in ("1", "true", "yes"):  # explicit refresh
            need_refresh = True
        if not rows:  # nothing in DB for range, try to populate
            need_refresh = True

        if need_refresh:
            inserted_any = False
            # Try FMP first
            fmp_key = (os.getenv("FMP_API_KEY") or "").strip()
            if fmp_key:
                try:
                    items = await fetch_earnings_calendar_fmp(start_d, end_d, fmp_key)
                except Exception:
                    items = []
                for it in items:
                    try:
                        ev_date = date.fromisoformat(it["event_date"])  # YYYY-MM-DD
                    except Exception:
                        continue
                    sym = it["ticker"].upper()
                    ex = (
                        s.query(EarningsEvent)
                        .filter(EarningsEvent.ticker == sym, EarningsEvent.event_date == ev_date)
                        .first()
                    )
                    if ex is None:
                        s.add(
                            EarningsEvent(
                                id=str(uuid.uuid4()),
                                ticker=sym,
                                company=it.get("company"),
                                event_date=ev_date,
                                time_of_day=it.get("time_of_day"),
                                status=it.get("status") or "upcoming",
                                source="fmp",
                            )
                        )
                    else:
                        # update missing fields
                        if not ex.company and it.get("company"):
                            ex.company = it.get("company")
                        if not ex.time_of_day and it.get("time_of_day"):
                            ex.time_of_day = it.get("time_of_day")
                        if not ex.status and it.get("status"):
                            ex.status = it.get("status")
                if items:
                    inserted_any = True

            # If FMP didn't return, try Finnhub
            if not inserted_any:
                fh_key = (os.getenv("FINNHUB_API_KEY") or "").strip()
                if fh_key:
                    try:
                        items = await fetch_earnings_calendar_finnhub(start_d, end_d, fh_key)
                    except Exception:
                        items = []
                    for it in items:
                        try:
                            ev_date = date.fromisoformat(it["event_date"])  # YYYY-MM-DD
                        except Exception:
                            continue
                        sym = it["ticker"].upper()
                        ex = (
                            s.query(EarningsEvent)
                            .filter(EarningsEvent.ticker == sym, EarningsEvent.event_date == ev_date)
                            .first()
                        )
                        if ex is None:
                            s.add(
                                EarningsEvent(
                                    id=str(uuid.uuid4()),
                                    ticker=sym,
                                    company=it.get("company"),
                                    event_date=ev_date,
                                    time_of_day=it.get("time_of_day"),
                                    status=it.get("status") or "upcoming",
                                    source="finnhub",
                                )
                            )
                        else:
                            if not ex.company and it.get("company"):
                                ex.company = it.get("company")
                            if not ex.time_of_day and it.get("time_of_day"):
                                ex.time_of_day = it.get("time_of_day")
                            if not ex.status and it.get("status"):
                                ex.status = it.get("status")

            # requery after attempts
            rows = q.all()

        return [
            EarningsEventOut(
                id=r.id,
                ticker=r.ticker,
                company=r.company,
                event_date=_iso(r.event_date),
                time_of_day=r.time_of_day,
                status=r.status,
            )
            for r in rows
        ]


@router.get("/earnings/summary/{ticker}", response_model=EarningsSummaryOut)
async def earnings_summary(ticker: str, limit: int = 4) -> EarningsSummaryOut:
    t = (ticker or "").upper()
    if not t:
        raise HTTPException(status_code=400, detail="ticker is required")
    # Keys
    fh_key = (os.getenv("FINNHUB_API_KEY") or "").strip()
    av_key = (os.getenv("ALPHA_VANTAGE_API_KEY") or "").strip()
    # Fetch concurrently
    tasks = []
    if fh_key:
        tasks.append(finnhub_eps(t, fh_key, limit=limit))
    if av_key:
        tasks.append(av_eps(t, av_key, limit=limit))
    results: List[List[dict]] = []
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=False)
    # Flatten + annotate providers are already in payload
    eps_items: List[dict] = []
    for lst in results:
        eps_items.extend(lst or [])
    # Deduplicate by (period, reported_eps) best-effort
    seen = set()
    dedup: List[dict] = []
    for it in eps_items:
        k = (it.get("period"), it.get("reported_eps"))
        if k in seen:
            continue
        seen.add(k)
        dedup.append(it)
    latest = _pick_latest(dedup)
    # Try to enrich company from DB events
    company: Optional[str] = None
    if is_db_enabled():
        with db_session() as s:
            ev = (
                s.query(EarningsEvent)
                .filter(EarningsEvent.ticker == t)
                .order_by(EarningsEvent.event_date.desc())
                .first()
            )
            company = ev.company if ev else None
    # Sources
    srcs = []
    if fh_key:
        srcs.append("finnhub")
    if av_key:
        srcs.append("alpha_vantage")
    return EarningsSummaryOut(
        ticker=t,
        company=company,
        latest=(EPSSurpriseItem(**latest) if latest else None),
        eps=[EPSSurpriseItem(**x) for x in dedup[:limit]],
        sources=srcs,
    )


@router.get("/earnings/summaries/today", response_model=List[EarningsSummaryOut])
async def earnings_summaries_today(limit: int = 10, per_ticker: int = 4) -> List[EarningsSummaryOut]:
    # Determine today tickers
    today = date.today()
    tickers: List[str] = []
    if is_db_enabled():
        with db_session() as s:
            rows = (
                s.query(EarningsEvent.ticker)
                .filter(EarningsEvent.event_date == today)
                .order_by(EarningsEvent.ticker.asc())
                .all()
            )
            tickers = [t for (t,) in rows][: max(1, min(int(limit), len(rows)))]
    if not tickers:
        # Fallback: query providers for today range to get symbols
        fh_key = (os.getenv("FINNHUB_API_KEY") or "").strip()
        fmp_key = (os.getenv("FMP_API_KEY") or "").strip()
        start_d, end_d = today, today
        if fh_key:
            try:
                items = await fetch_earnings_calendar_finnhub(start_d, end_d, fh_key)
                tickers = [it["ticker"].upper() for it in items][:limit]
            except Exception:
                pass
        if not tickers and fmp_key:
            try:
                items = await fetch_earnings_calendar_fmp(start_d, end_d, fmp_key)
                tickers = [it["ticker"].upper() for it in items][:limit]
            except Exception:
                pass
    if not tickers:
        return []
    # Build summaries concurrently
    async def _one(tk: str):
        try:
            return await earnings_summary(tk, limit=per_ticker)
        except Exception:
            return EarningsSummaryOut(ticker=tk, company=None, latest=None, eps=[], sources=[])
    outs = await asyncio.gather(*[_one(t) for t in tickers])
    return outs


def _highlights_range(kind: str) -> tuple[date, date]:
    today = date.today()
    if kind == "today":
        return today, today
    # this_week: Monday..Sunday of current week
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


@router.get("/highlights/today", response_model=List[HighlightOut])
async def highlights_today(limit: int = 20) -> List[HighlightOut]:
    return await _highlights_generic("today", limit)


@router.get("/highlights/this_week", response_model=List[HighlightOut])
async def highlights_this_week(limit: int = 50) -> List[HighlightOut]:
    return await _highlights_generic("this_week", limit)


@router.get("/ticker/{ticker}/highlights", response_model=List[HighlightOut])
async def highlights_for_ticker(ticker: str, limit: int = 10) -> List[HighlightOut]:
    if not is_db_enabled():
        # Fallback placeholder
        now = datetime.utcnow()
        return [
            HighlightOut(
                id=str(uuid.uuid4()),
                ticker=ticker.upper(),
                company=None,
                summary={"note": "DB disabled; placeholder highlight"},
                rank_score=None,
                created_at=now.isoformat(),
            )
        ]
    with db_session() as s:
        rows: List[Highlight] = (
            s.query(Highlight)
            .filter(Highlight.ticker == ticker.upper())
            .order_by(Highlight.created_at.desc())
            .limit(limit)
            .all()
        )
        out: List[HighlightOut] = []
        # Optionally join to events to obtain company; for now use last event if exists
        # (Simple approach to avoid an extra join)
        comp_map: dict[str, str] = {}
        ev = s.query(EarningsEvent).filter(EarningsEvent.ticker == ticker.upper()).order_by(EarningsEvent.event_date.desc()).first()
        company = ev.company if ev else None
        for r in rows:
            out.append(
                HighlightOut(
                    id=r.id,
                    ticker=r.ticker,
                    company=company,
                    summary=r.summary_json or {},
                    rank_score=r.rank_score,
                    created_at=_iso(r.created_at),
                )
            )
        return out


async def _highlights_generic(kind: str, limit: int) -> List[HighlightOut]:
    if not is_db_enabled():
        now = datetime.utcnow()
        return [
            HighlightOut(
                id=str(uuid.uuid4()),
                ticker="AAPL",
                company="Apple Inc.",
                summary={"rev": {"status": "beat", "pct": 3.1}, "eps": {"status": "beat", "pct": 2.2}, "bullets": ["iPhone ASP up", "Services +12% y/y"]},
                rank_score=0.9,
                created_at=now.isoformat(),
            )
        ]
    start, end = _highlights_range("today" if kind == "today" else "this_week")
    with db_session() as s:
        rows: List[Highlight] = (
            s.query(Highlight)
            .filter(func.date(Highlight.created_at) >= start, func.date(Highlight.created_at) <= end)
            .order_by(Highlight.rank_score.desc().nullslast(), Highlight.created_at.desc())
            .limit(limit)
            .all()
        )
        # Try to attach company names from latest events per ticker
        companies: dict[str, Optional[str]] = {}
        tickers = list({r.ticker for r in rows})
        if tickers:
            evs = (
                s.query(EarningsEvent)
                .filter(EarningsEvent.ticker.in_(tickers))
                .order_by(EarningsEvent.ticker.asc(), EarningsEvent.event_date.desc())
                .all()
            )
            for e in evs:
                if e.ticker not in companies:
                    companies[e.ticker] = e.company
        out: List[HighlightOut] = []
        for r in rows:
            out.append(
                HighlightOut(
                    id=r.id,
                    ticker=r.ticker,
                    company=companies.get(r.ticker),
                    summary=r.summary_json or {},
                    rank_score=r.rank_score,
                    created_at=_iso(r.created_at),
                )
            )
        return out
