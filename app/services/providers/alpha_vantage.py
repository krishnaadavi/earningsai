from __future__ import annotations

from typing import List, Dict, Any
import httpx

from app.services.metrics import now, elapsed_ms, record_http

ALPHAVANTAGE_BASE = "https://www.alphavantage.co/query"


async def fetch_quarterly_earnings(ticker: str, api_key: str, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Fetch recent quarterly earnings (EPS) from Alpha Vantage.
    Normalized fields per item: { period, reported_eps, estimated_eps, surprise, surprise_pct }
    Docs: https://www.alphavantage.co/documentation/#earnings
    """
    if not api_key or not ticker:
        return []
    params = {"function": "EARNINGS", "symbol": ticker.upper(), "apikey": api_key}
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        t0 = now()
        try:
            resp = await client.get(ALPHAVANTAGE_BASE, params=params)
            record_http("alpha_vantage", "/query/EARNINGS", resp.status_code, elapsed_ms(t0))
            if resp.status_code >= 400:
                return []
            data = resp.json() or {}
        except Exception:
            record_http("alpha_vantage", "/query/EARNINGS", 0, elapsed_ms(t0))
            return []
        q = data.get("quarterlyEarnings") or []
        out: List[Dict[str, Any]] = []
        for it in q[: max(1, min(int(limit), len(q)) )]:
            try:
                out.append({
                    "period": (it.get("fiscalDateEnding") or ""),
                    "reported_eps": _to_float(it.get("reportedEPS")),
                    "estimated_eps": _to_float(it.get("estimatedEPS")),
                    "surprise": _to_float(it.get("surprise")),
                    "surprise_pct": _to_float(it.get("surprisePercentage")),
                    "provider": "alpha_vantage",
                })
            except Exception:
                continue
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
