from __future__ import annotations

import time
import contextvars
from typing import Any, Dict, Optional, List
from statistics import median

# Context-local aggregator for a single job run (ingest_today or refresh_next_14_days)
metrics_ctx: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("ingestion_metrics", default=None)


def now() -> float:
    return time.perf_counter()


def elapsed_ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def make_aggregator() -> Dict[str, Any]:
    return {
        "provider": {},   # provider -> { req, status: {code: n}, latency_ms: [ms], endpoints: {path: {...}} }
        "llm": {},        # provider/model -> { calls, tokens_in, tokens_out, cost_usd, latency_ms: [ms], errors }
    }


def begin_run() -> None:
    metrics_ctx.set(make_aggregator())


def _percentile(values: List[int], p: float) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return int(s[k])


def _summarize_latencies(values: List[int]) -> Dict[str, Optional[int]]:
    if not values:
        return {"p50": None, "p95": None, "p99": None, "max": None}
    return {
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
        "max": max(values) if values else None,
    }


def end_run() -> Dict[str, Any]:
    agg = metrics_ctx.get() or {}
    out: Dict[str, Any] = {"provider": {}, "llm": {}}
    prov: Dict[str, Any] = agg.get("provider") or {}
    for name, v in prov.items():
        if not isinstance(v, dict):
            continue
        # Special-case fallback counters bucket
        if name == "fallbacks" and ("req" not in v and "status" not in v):
            out["provider"]["fallbacks"] = {"counts": v}
            continue
        entry = {
            "req": int(v.get("req", 0)),
            "status": v.get("status", {}),
            "latency": _summarize_latencies(v.get("latency_ms", []) or []),
        }
        eps = {}
        for ep, ev in (v.get("endpoints") or {}).items():
            eps[ep] = {
                "req": int(ev.get("req", 0)),
                "status": ev.get("status", {}),
                "latency": _summarize_latencies(ev.get("latency_ms", []) or []),
            }
        if eps:
            entry["endpoints"] = eps
        out["provider"][name] = entry

    llm: Dict[str, Any] = agg.get("llm") or {}
    for key, v in llm.items():
        out["llm"][key] = {
            "calls": int(v.get("calls", 0)),
            "tokens_in": int(v.get("tokens_in", 0)),
            "tokens_out": int(v.get("tokens_out", 0)),
            "cost_usd": float(v.get("cost_usd", 0.0)),
            "errors": int(v.get("errors", 0)),
            "latency": _summarize_latencies(v.get("latency_ms", []) or []),
        }
    return out


def record_http(provider: str, endpoint: str, status: int, latency_ms: int) -> None:
    agg = metrics_ctx.get()
    if agg is None:
        return
    prov = agg["provider"].setdefault(provider, {"req": 0, "status": {}, "latency_ms": [], "endpoints": {}})
    prov["req"] += 1
    code_key = str(int(status))
    prov["status"][code_key] = int(prov["status"].get(code_key, 0)) + 1
    prov["latency_ms"].append(int(latency_ms))
    ep = prov["endpoints"].setdefault(endpoint, {"req": 0, "status": {}, "latency_ms": []})
    ep["req"] += 1
    ep["status"][code_key] = int(ep["status"].get(code_key, 0)) + 1
    ep["latency_ms"].append(int(latency_ms))


def record_fallback(kind: str) -> None:
    agg = metrics_ctx.get()
    if agg is None:
        return
    fb = agg["provider"].setdefault("fallbacks", {})
    fb[kind] = int(fb.get(kind, 0)) + 1


def record_llm(provider: str, model: str, *, tokens_in: int = 0, tokens_out: int = 0, cost_usd: float = 0.0, latency_ms: int = 0, ok: bool = True) -> None:
    agg = metrics_ctx.get()
    if agg is None:
        return
    key = f"{provider}:{model}"
    llm = agg["llm"].setdefault(key, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency_ms": [], "errors": 0})
    llm["calls"] += 1
    llm["tokens_in"] += int(tokens_in)
    llm["tokens_out"] += int(tokens_out)
    llm["cost_usd"] = float(llm["cost_usd"]) + float(cost_usd or 0.0)
    if latency_ms:
        llm["latency_ms"].append(int(latency_ms))
    if not ok:
        llm["errors"] += 1
