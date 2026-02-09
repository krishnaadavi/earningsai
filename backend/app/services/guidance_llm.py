from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.types import Chunk, Citation

DEFAULT_MODEL = os.getenv("GUIDANCE_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = (
    "You are an expert financial analyst focused on quarterly earnings guidance. "
    "Given chunks from an earnings call or filing, extract structured forward guidance. "
    "Respond ONLY with valid JSON containing a list of guidance items."
)


def _client():
    from openai import OpenAI  # lazy import to avoid cost if unused

    return OpenAI()


def _make_chunk_label(idx: int) -> str:
    return f"C{idx + 1}"


def build_prompt(chunks: List[Chunk], meta: Optional[Dict[str, Any]] = None) -> str:
    """Format candidate chunks into a single prompt string."""
    header = [
        "You will receive a set of text excerpts from an earnings document.",
        "Each excerpt is labeled C1, C2, etc. Always cite the chunk id in your JSON output.",
        "Output format (JSON array):",
        "[",
        "  {",
        "    \"chunk_id\": \"C1\",",
        "    \"metric\": \"revenue\",",
        "    \"period\": \"Q3 FY24\",",
        "    \"value_low\": 12000,",
        "    \"value_high\": 12300,",
        "    \"value_point\": null,",
        "    \"unit\": \"USD_millions\",",
        "    \"outlook_note\": \"Margins expected to remain flat.\",",
        "    \"confidence\": \"medium\"",
        "  }",
        "]",
        "If no guidance is found, return an empty JSON array [].",
    ]
    if meta:
        ticker = (meta.get("ticker") or "").upper()
        company = meta.get("company")
        if ticker or company:
            header.append(
                f"Document context: ticker={ticker or 'N/A'}, company={company or 'N/A'}."
            )
    body = []
    for idx, chunk in enumerate(chunks):
        label = _make_chunk_label(idx)
        section = chunk.section or "Unknown section"
        body.append(
            f"[{label} | page {chunk.page_start}-{chunk.page_end} | {section}]\n{chunk.text.strip()}"
        )
    return "\n".join(header + ["\nChunks:"] + body)


@retry(reraise=True, stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=0.5, max=2))
def _raw_completion(prompt: str) -> str:
    client = _client()
    resp = client.chat.completions.create(
        model=DEFAULT_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _extract_json(raw: str) -> List[Dict[str, Any]]:
    raw = raw.strip()
    if not raw:
        return []
    # Attempt direct parse first
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # Look for first JSON array in output
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        snippet = raw[start : end + 1]
        try:
            data = json.loads(snippet)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return []


def _sanitize_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    chunk_id = entry.get("chunk_id")
    metric = entry.get("metric")
    period = entry.get("period")
    value_low = entry.get("value_low")
    value_high = entry.get("value_high")
    value_point = entry.get("value_point")
    unit = entry.get("unit")
    outlook_note = entry.get("outlook_note")
    confidence = entry.get("confidence")
    # Ensure numeric fields are floats when provided
    def _to_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    clean = {
        "chunk_id": chunk_id if isinstance(chunk_id, str) else None,
        "metric": metric if isinstance(metric, str) else None,
        "period": period if isinstance(period, str) else None,
        "value_low": _to_float(value_low),
        "value_high": _to_float(value_high),
        "value_point": _to_float(value_point),
        "unit": unit if isinstance(unit, str) else None,
        "outlook_note": outlook_note if isinstance(outlook_note, str) else None,
        "confidence": confidence if isinstance(confidence, str) else None,
    }
    if not any([clean["value_low"], clean["value_high"], clean["value_point"], clean["outlook_note"]]):
        # Require at least one meaningful field
        return None
    return clean


def generate_guidance_entries(chunks: List[Chunk], meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Call OpenAI to produce structured guidance entries for given chunks."""
    if not chunks or not os.getenv("OPENAI_API_KEY"):
        return []
    prompt = build_prompt(chunks, meta=meta)
    try:
        raw = _raw_completion(prompt)
    except Exception:
        return []
    entries = _extract_json(raw)
    clean_entries: List[Dict[str, Any]] = []
    for entry in entries:
        sanitized = _sanitize_entry(entry)
        if sanitized:
            clean_entries.append(sanitized)
    return clean_entries


def attach_citations(entries: List[Dict[str, Any]], chunk_map: Dict[str, Chunk]) -> List[Dict[str, Any]]:
    """Attach citation objects based on chunk ids returned by the model."""
    out: List[Dict[str, Any]] = []
    for entry in entries:
        chunk_id = entry.get("chunk_id")
        chunk = chunk_map.get(chunk_id or "") if chunk_id else None
        citations: List[Citation] = []
        if chunk:
            citations.append(
                Citation(
                    section=chunk.section,
                    page=chunk.page_start,
                    snippet=chunk.text[:160],
                )
            )
        out.append({**entry, "citations": [c.dict() for c in citations]})
    return out
