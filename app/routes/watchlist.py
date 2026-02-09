from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_

from app.db.base import db_session
from app.db.models import Watchlist, EarningsEvent
from app.db.persistence import is_db_enabled

router = APIRouter()


class WatchlistOut(BaseModel):
    id: str
    ticker: str


@router.get("/watchlist", response_model=List[WatchlistOut])
async def list_watchlist(user_id: Optional[str] = Query(default=None)) -> List[WatchlistOut]:
    if not is_db_enabled():
        return []
    with db_session() as s:
        rows = s.query(Watchlist).all()
        return [WatchlistOut(id=r.id, ticker=r.ticker) for r in rows]


@router.post("/watchlist/{ticker}", response_model=WatchlistOut)
async def add_watchlist(ticker: str, user_id: Optional[str] = Query(default=None)) -> WatchlistOut:
    if not is_db_enabled():
        raise HTTPException(status_code=400, detail="DB not enabled")
    sym = ticker.upper()
    with db_session() as s:
        ex = s.query(Watchlist).filter(Watchlist.ticker == sym).first()
        if ex:
            return WatchlistOut(id=ex.id, ticker=ex.ticker)
        w = Watchlist(id=str(uuid.uuid4()), user_id=user_id, ticker=sym)
        s.add(w)
        s.flush()
        return WatchlistOut(id=w.id, ticker=w.ticker)


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str, user_id: Optional[str] = Query(default=None)) -> dict:
    if not is_db_enabled():
        raise HTTPException(status_code=400, detail="DB not enabled")
    sym = ticker.upper()
    with db_session() as s:
        ex = s.query(Watchlist).filter(Watchlist.ticker == sym).first()
        if ex:
            s.delete(ex)
        return {"status": "ok"}


class EventOut(BaseModel):
    id: str
    ticker: str
    company: Optional[str] = None
    event_date: str
    time_of_day: Optional[str] = None
    status: Optional[str] = None


@router.get("/watchlist/events", response_model=List[EventOut])
async def watchlist_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user_id: Optional[str] = Query(default=None),
) -> List[EventOut]:
    if not is_db_enabled():
        return []
    try:
        start_d = date.fromisoformat(start) if start else date.today() - timedelta(days=3)
        end_d = date.fromisoformat(end) if end else date.today() + timedelta(days=7)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD")

    with db_session() as s:
        w_tickers = [w.ticker for w in s.query(Watchlist).all()]
        if not w_tickers:
            return []
        rows = (
            s.query(EarningsEvent)
            .filter(
                and_(
                    EarningsEvent.event_date >= start_d,
                    EarningsEvent.event_date <= end_d,
                    EarningsEvent.ticker.in_(w_tickers),
                )
            )
            .order_by(EarningsEvent.event_date.asc(), EarningsEvent.ticker.asc())
            .all()
        )
        return [
            EventOut(
                id=r.id,
                ticker=r.ticker,
                company=r.company,
                event_date=r.event_date.isoformat(),
                time_of_day=r.time_of_day,
                status=r.status,
            )
            for r in rows
        ]
