from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.models.types import Chunk, Citation

# Simple, deterministic heuristic extractors for P1
# Notes:
# - We favor deterministic regex-based extraction with clear citations
# - If OPENAI is available later, we can augment with an LLM pass

MONEY_RE = re.compile(r"\$?([0-9][0-9,\.]*)\s*(b|bn|billion|m|mm|million|k|thousand)?", re.I)
PCT_RE = re.compile(r"([0-9]{1,2}(?:\.[0-9]+)?)\s*%")
PERIOD_RE = re.compile(r"\b((Q[1-4]|FY)\s*\d{4})\b", re.I)


def _to_millions(value_str: str, unit: Optional[str]) -> float:
    num = float(value_str.replace(",", ""))
    if not unit:
        return num
    u = unit.lower()
    if u in ("b", "bn", "billion"):
        return num * 1_000
    if u in ("m", "mm", "million"):
        return num
    if u in ("k", "thousand"):
        return num / 1_000
    return num


def _first_money(text: str) -> Optional[float]:
    m = MONEY_RE.search(text)
    if not m:
        return None
    return _to_millions(m.group(1), m.group(2))


def _first_pct(text: str) -> Optional[float]:
    m = PCT_RE.search(text)
    if not m:
        return None
    return float(m.group(1))


def _first_period(text: str) -> Optional[str]:
    m = PERIOD_RE.search(text)
    return m.group(1).upper() if m else None


class MetricMatch:
    def __init__(self, name: str, value: float, unit: str, period: Optional[str], chunk: Chunk):
        self.name = name
        self.value = value
        self.unit = unit
        self.period = period
        self.chunk = chunk

    def to_dict(self) -> Dict:
        cit = Citation(section=self.chunk.section, page=self.chunk.page_start, snippet=self.chunk.text[:160])
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "period": self.period,
            "citations": [cit],
        }


def extract_core_metrics(chunks: List[Chunk]) -> Dict[str, Dict]:
    """
    Extract core metrics with simple rules and provide citations from the matched chunk.
    Metrics:
      - revenue (USD millions)
      - gross_margin (%)
      - operating_margin (%)
      - eps_gaap (USD)
      - eps_nongaap (USD)
      - cfo (USD millions)
      - capex (USD millions)
      - fcf (USD millions; cfo - capex if both found)
      - fcf_margin (%)
    """
    found: Dict[str, MetricMatch] = {}

    for c in chunks:
        txt = c.text
        ltxt = txt.lower()
        period = _first_period(txt)

        # Revenue
        if "revenue" in ltxt and "deferred" not in ltxt:
            val = _first_money(txt)
            if val is not None and "revenue" not in found:
                found["revenue"] = MetricMatch("revenue", val, "USD_millions", period, c)

        # Gross margin
        if "gross margin" in ltxt:
            pct = _first_pct(txt)
            if pct is not None and "gross_margin" not in found:
                found["gross_margin"] = MetricMatch("gross_margin", pct, "percent", period, c)

        # Operating margin
        if "operating margin" in ltxt or ("operating income" in ltxt and "%" in ltxt):
            pct = _first_pct(txt)
            if pct is not None and "operating_margin" not in found:
                found["operating_margin"] = MetricMatch("operating_margin", pct, "percent", period, c)

        # EPS GAAP / Non-GAAP
        if "earnings per share" in ltxt or "eps" in ltxt:
            val = _first_money(txt)
            if val is not None:
                # EPS values in text are already per-share USD (e.g., $1.23), not millions
                if ("non-gaap" in ltxt or "adjusted" in ltxt or "non gaap" in ltxt) and "eps_nongaap" not in found:
                    found["eps_nongaap"] = MetricMatch("eps_nongaap", val, "USD", period, c)
                elif "eps_gaap" not in found:
                    found["eps_gaap"] = MetricMatch("eps_gaap", val, "USD", period, c)

        # CFO
        if "cash provided by operating activities" in ltxt or "operating cash flow" in ltxt or "cash flow from operations" in ltxt:
            val = _first_money(txt)
            if val is not None and "cfo" not in found:
                found["cfo"] = MetricMatch("cfo", val, "USD_millions", period, c)

        # CAPEX
        if "capital expenditures" in ltxt or "capex" in ltxt or "property and equipment" in ltxt:
            val = _first_money(txt)
            if val is not None and "capex" not in found:
                found["capex"] = MetricMatch("capex", val, "USD_millions", period, c)

        # FCF / FCF margin
        if "free cash flow" in ltxt or "fcf" in ltxt:
            mval = _first_money(txt)
            if mval is not None and "fcf" not in found:
                found["fcf"] = MetricMatch("fcf", mval, "USD_millions", period, c)
            mpct = _first_pct(txt)
            if mpct is not None and "fcf_margin" not in found:
                found["fcf_margin"] = MetricMatch("fcf_margin", mpct, "percent", period, c)

    # Derive FCF if not explicitly found
    if "fcf" not in found and "cfo" in found and "capex" in found:
        cfo = found["cfo"].value
        capex = found["capex"].value
        # FCF = CFO - CAPEX
        fcf_val = cfo - capex
        c_period = found["cfo"].period or found["capex"].period
        found["fcf"] = MetricMatch("fcf", fcf_val, "USD_millions", c_period, found["cfo"].chunk)

    return {name: mm.to_dict() for name, mm in found.items()}


def extract_series_for_metrics(chunks: List[Chunk], metrics: List[str]) -> Dict[str, Dict[str, List]]:
    """Very simple series extractor: scan lines for period+value pairs.
    Returns mapping metric -> {labels:[], values:[], citations:[Citation]}
    """
    series_map: Dict[str, Dict[str, List]] = {}

    text = "\n".join(c.text for c in chunks)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # For now, treat revenue-like metrics as money, margins as pct, EPS as money but non-scaled
    def metric_kind(m: str) -> str:
        m = m.lower()
        if "margin" in m:
            return "pct"
        if m.startswith("eps"):
            return "eps"
        return "money"

    for mname in metrics:
        labels: List[str] = []
        values: List[float] = []
        cit: Optional[Citation] = None
        kind = metric_kind(mname)
        for line in lines:
            per = _first_period(line)
            if not per:
                continue
            if kind == "pct":
                val = _first_pct(line)
            elif kind == "eps":
                mv = _first_money(line)
                val = mv if mv is not None else None
            else:
                val = _first_money(line)
            if val is not None:
                labels.append(per)
                values.append(val)
        if labels and values:
            # citation from first matching chunk
            for c in chunks:
                if labels[0] in c.text:
                    cit = Citation(section=c.section, page=c.page_start, snippet=c.text[:160])
                    break
            series_map[mname] = {
                "labels": labels[:8],
                "values": values[:8],
                "citations": [cit] if cit else [],
            }
    return series_map


def extract_guidance(chunks: List[Chunk]) -> Dict:
    """Extract simple forward-looking guidance heuristics with citations."""
    out: List[Dict] = []
    for c in chunks:
        txt = c.text
        ltxt = txt.lower()
        if any(k in ltxt for k in ["guidance", "outlook", "expects", "forecast"]):
            # Try to capture any range like $X to $Y or A% to B%
            m_money = re.search(r"\$?([0-9][0-9,\.]*)\s*(b|bn|billion|m|mm|million|k|thousand)?\s*(?:to|-)\s*\$?([0-9][0-9,\.]*)\s*(b|bn|billion|m|mm|million|k|thousand)?", txt, re.I)
            m_pct = re.search(r"([0-9]{1,2}(?:\.[0-9]+)?)\s*%\s*(?:to|-)\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%", txt, re.I)
            per = _first_period(txt)
            if m_money:
                lo = _to_millions(m_money.group(1), m_money.group(2))
                hi = _to_millions(m_money.group(3), m_money.group(4))
                out.append({
                    "type": "revenue",
                    "range": [lo, hi],
                    "unit": "USD_millions",
                    "period": per,
                    "citations": [Citation(section=c.section, page=c.page_start, snippet=txt[:160])],
                })
            if m_pct:
                lo = float(m_pct.group(1))
                hi = float(m_pct.group(2))
                out.append({
                    "type": "margin",
                    "range": [lo, hi],
                    "unit": "percent",
                    "period": per,
                    "citations": [Citation(section=c.section, page=c.page_start, snippet=txt[:160])],
                })
    return {"guidance": out}


def extract_buybacks(chunks: List[Chunk]) -> Dict:
    out: Dict = {"buybacks": []}
    for c in chunks:
        ltxt = c.text.lower()
        if "repurchase" in ltxt or "buyback" in ltxt or "share repurchase" in ltxt:
            m_auth = re.search(r"authorize(?:d|s|tion).*?\$?([0-9][0-9,\.]*)\s*(b|bn|billion|m|mm|million|k|thousand)?", c.text, re.I)
            m_exec = re.search(r"repurchase(?:d)?.*?\$?([0-9][0-9,\.]*)\s*(b|bn|billion|m|mm|million|k|thousand)?", c.text, re.I)
            per = _first_period(c.text)
            item: Dict = {"period": per, "citations": [Citation(section=c.section, page=c.page_start, snippet=c.text[:160])]} 
            if m_auth:
                item["authorization_amount"] = _to_millions(m_auth.group(1), m_auth.group(2))
                item["unit"] = "USD_millions"
            if m_exec:
                item["repurchased_amount"] = _to_millions(m_exec.group(1), m_exec.group(2))
                item["unit"] = "USD_millions"
            out["buybacks"].append(item)
    return out
