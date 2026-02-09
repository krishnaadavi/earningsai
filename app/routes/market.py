from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Dict, Any
import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_

from app.db.base import db_session
from app.db.models import EarningsEvent, Watchlist
from app.db.persistence import is_db_enabled

router = APIRouter()


class MoverOut(BaseModel):
    ticker: str
    company: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    direction: Optional[str] = None  # up/down/flat
    source: Optional[str] = None


async def _fetch_quote(client: httpx.AsyncClient, sym: str, api_key: str) -> Dict[str, Any]:
    url = "https://finnhub.io/api/v1/quote"
    try:
        r = await client.get(url, params={"symbol": sym, "token": api_key}, timeout=8.0)
        if r.status_code >= 400:
            return {"ticker": sym}
        q = r.json() or {}
        c = q.get("c")  # current
        pc = q.get("pc")  # prev close
        d = q.get("d")
        dp = q.get("dp")
        if dp is None and (c is not None) and (pc not in (None, 0)):
            try:
                dp = (float(c) - float(pc)) / float(pc) * 100.0
            except Exception:
                dp = None
        direction = "flat"
        if isinstance(dp, (int, float)):
            direction = "up" if dp >= 0 else "down"
        return {
            "ticker": sym,
            "price": c,
            "change": d,
            "change_percent": dp,
            "direction": direction,
            "source": "finnhub",
        }
    except Exception:
        return {"ticker": sym}


@router.get("/market/movers", response_model=List[MoverOut])
async def market_movers(tickers: Optional[str] = None, limit: int = 20) -> List[MoverOut]:
    """Return top movers by abs % change among provided tickers or inferred set.
    Inferred set = today's earnings + watchlist (if DB enabled).
    """
    api_key = (os.getenv("FINNHUB_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="FINNHUB_API_KEY not configured")

    sym_set: List[str] = []
    if tickers:
        sym_set = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    elif is_db_enabled():
        today = date.today()
        with db_session() as s:
            ev = (
                s.query(EarningsEvent.ticker, EarningsEvent.company)
                .filter(EarningsEvent.event_date == today)
                .all()
            )
            wl = s.query(Watchlist.ticker).all()
        # Flatten and uniquify
        sym_set = list({*(t for t, *_ in ev), *(t for (t,) in wl)})
    # Fallback if empty
    if not sym_set:
        raise HTTPException(status_code=400, detail="No tickers available to scan")

    # Cap how many we fetch to respect rate limits
    sym_set = sym_set[: max(1, min(limit * 3, 50))]

    results: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for i in range(0, len(sym_set), 8):  # small batches
            batch = sym_set[i : i + 8]
            try:
                quotes = await asyncio.gather(
                    *[_fetch_quote(client, s, api_key) for s in batch],
                    return_exceptions=True,
                )
                cleaned: List[Dict[str, Any]] = []
                for q in quotes:
                    if isinstance(q, Exception):
                        continue
                    cleaned.append(q)
                results.extend(cleaned)
            except Exception:
                # sequential fallback if gather fails
                for s in batch:
                    results.append(await _fetch_quote(client, s, api_key))

    # Sort by abs change_percent desc
    def key_fn(it: Dict[str, Any]):
        dp = it.get("change_percent")
        return abs(float(dp)) if isinstance(dp, (int, float)) else -1.0

    results = sorted(results, key=key_fn, reverse=True)
    # Trim
    results = results[: limit]

    # Attach company if we have it for today's events
    if is_db_enabled():
        today = date.today()
        company_map: Dict[str, Optional[str]] = {}
        with db_session() as s:
            rows = (
                s.query(EarningsEvent.ticker, EarningsEvent.company)
                .filter(EarningsEvent.event_date == today)
                .all()
            )
            for t, c in rows:
                company_map[t] = c
        for it in results:
            t = it.get("ticker")
            if t and t in company_map and not it.get("company"):
                it["company"] = company_map[t]

    return [MoverOut(**it) for it in results]
