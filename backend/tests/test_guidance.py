import os
import json

from app.services.guidance_llm import _extract_json, _sanitize_entry
from app.services.guidance_enricher import _heuristic_fallback
from app.models.types import Chunk


def test_extract_json_variants():
    raw1 = "[]"
    raw2 = "some preface\n[ {\"metric\": \"revenue\"} ]\ntrailing"
    raw3 = "not json"

    assert _extract_json(raw1) == []
    parsed = _extract_json(raw2)
    assert isinstance(parsed, list)
    assert parsed and parsed[0].get("metric") == "revenue"
    assert _extract_json(raw3) == []


def test_sanitize_entry_numbers_and_required_fields():
    ok = _sanitize_entry({
        "chunk_id": "C1",
        "metric": "revenue",
        "period": "Q3 FY24",
        "value_low": "123",
        "value_high": 130,
        "value_point": None,
        "unit": "USD_millions",
        "outlook_note": "Flat margins",
        "confidence": "medium",
    })
    assert ok is not None
    assert ok["value_low"] == 123.0
    assert ok["value_high"] == 130.0

    # Missing meaningful fields should return None
    bad = _sanitize_entry({"metric": "revenue"})
    assert bad is None


def test_heuristic_fallback_normalizes_to_enriched_schema():
    chunks = [
        Chunk(
            id="c1",
            text="We provide guidance: revenue expected to be $100 to $120 million for Q3 FY2024.",
            section="Outlook",
            page_start=5,
            page_end=5,
        )
    ]
    out = _heuristic_fallback(chunks)
    assert isinstance(out, list)
    assert len(out) >= 1
    item = out[0]
    # normalized fields exist
    assert set(["metric", "period", "value_low", "value_high", "unit"]).issubset(item.keys())
    assert item["value_low"] <= item["value_high"]
