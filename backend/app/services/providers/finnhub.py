from __future__ import annotations

from datetime import date
from typing import List, Dict, Any
import httpx

FINNHUB_BASE = "https://finnhub.io/api/v1"


def _norm_time_of_day(hour: str | None) -> str | None:
    if not hour:
        return None
    h = hour.strip().lower()
    if h == "bmo":
        return "BMO"
    if h == "amc":
        return "AMC"
    return None


def _iso(d: date) -> str:
    return d.isoformat()


async def fetch_earnings_calendar(start: date, end: date, api_key: str) -> List[Dict[str, Any]]:
    """Fetch earnings calendar from Finnhub for [start, end].
    Returns a list of items with fields: ticker, company, event_date (YYYY-MM-DD), time_of_day, status, source.
    Docs:
      - https://finnhub.io/docs/api/calendar-earnings
    """
    if not api_key:
        return []
    params = {"from": _iso(start), "to": _iso(end), "token": api_key}
    url = f"{FINNHUB_BASE}/calendar/earnings"
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        if resp.status_code >= 400:
            return []
        data = resp.json() or {}
        cal = data.get("earningsCalendar") or []
        out: List[Dict[str, Any]] = []
        for it in cal:
            sym = (it.get("symbol") or "").upper()
            dt = (it.get("date") or "").split("T")[0]
            tod = _norm_time_of_day(it.get("hour"))
            comp = it.get("company") or None
            if not sym or not dt:
                continue
            out.append({
                "ticker": sym,
                "company": comp,
                "event_date": dt,
                "time_of_day": tod,
                "status": "upcoming",
                "source": "finnhub",
            })
        return out
