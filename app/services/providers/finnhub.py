from __future__ import annotations

from datetime import date
from typing import List, Dict, Any
import httpx
from app.services.metrics import now, elapsed_ms, record_http

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
        t0 = now()
        try:
            resp = await client.get(url, params=params)
            record_http("finnhub", "/calendar/earnings", resp.status_code, elapsed_ms(t0))
            if resp.status_code >= 400:
                return []
            data = resp.json() or {}
        except Exception:
            record_http("finnhub", "/calendar/earnings", 0, elapsed_ms(t0))
            return []
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


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s.endswith("%"):
            s = s[:-1]
        return float(s)
    except Exception:
        return None


async def fetch_eps_surprises(ticker: str, api_key: str, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Fetch historical EPS surprises for a ticker from Finnhub.
    Normalized item fields: { period, reported_eps, estimated_eps, surprise, surprise_pct }
    Docs: https://finnhub.io/docs/api/earnings
    """
    if not api_key or not ticker:
        return []
    params = {"symbol": ticker.upper(), "token": api_key}
    url = f"{FINNHUB_BASE}/stock/earnings"
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        t0 = now()
        try:
            resp = await client.get(url, params=params)
            record_http("finnhub", "/stock/earnings", resp.status_code, elapsed_ms(t0))
            if resp.status_code >= 400:
                return []
            data = resp.json() or []
        except Exception:
            record_http("finnhub", "/stock/earnings", 0, elapsed_ms(t0))
            return []
        out: List[Dict[str, Any]] = []
        # API returns most-recent first typically; enforce limit
        for it in data[: max(1, min(int(limit), len(data)) )]:
            try:
                out.append({
                    "period": (it.get("period") or it.get("date") or ""),
                    "reported_eps": _to_float(it.get("actual")),
                    "estimated_eps": _to_float(it.get("estimate")),
                    "surprise": _to_float(it.get("surprise")),
                    "surprise_pct": _to_float(it.get("surprisePercent")),
                    "provider": "finnhub",
                })
            except Exception:
                continue
        return out
