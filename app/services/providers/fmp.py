from __future__ import annotations

from datetime import date
from typing import List, Dict, Any
import httpx
from app.services.metrics import now, elapsed_ms, record_http

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _norm_time_of_day(raw: str | None) -> str | None:
    if not raw:
        return None
    r = raw.strip().lower()
    if r == "bmo":
        return "BMO"
    if r == "amc":
        return "AMC"
    return None


def _iso(d: date) -> str:
    return d.isoformat()


async def fetch_earnings_calendar(start: date, end: date, api_key: str) -> List[Dict[str, Any]]:
    """Fetch earnings calendar from FMP for [start, end].
    Returns a list of items with fields: ticker, company, event_date (YYYY-MM-DD), time_of_day.
    Docs:
      - https://site.financialmodelingprep.com/developer/docs/earnings-calendar-api/
    """
    if not api_key:
        return []
    params = {"from": _iso(start), "to": _iso(end), "apikey": api_key}
    url = f"{FMP_BASE}/earning_calendar"
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        t0 = now()
        try:
            resp = await client.get(url, params=params)
            record_http("fmp", "/earning_calendar", resp.status_code, elapsed_ms(t0))
            if resp.status_code >= 400:
                return []
            data = resp.json() or []
        except Exception:
            record_http("fmp", "/earning_calendar", 0, elapsed_ms(t0))
            return []
        out: List[Dict[str, Any]] = []
        for it in data:
            # FMP fields: symbol, date, time, company?
            sym = (it.get("symbol") or it.get("ticker") or "").upper()
            dt = (it.get("date") or it.get("dateTime") or "").split("T")[0]
            tod = _norm_time_of_day(it.get("time"))
            comp = it.get("company") or it.get("companyName") or None
            if not sym or not dt:
                continue
            out.append({
                "ticker": sym,
                "company": comp,
                "event_date": dt,
                "time_of_day": tod,
                "status": "upcoming",
                "source": "fmp",
            })
        return out
