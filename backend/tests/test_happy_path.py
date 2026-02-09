from fastapi.testclient import TestClient

from app.main import app
from app.models.types import Chunk
from app.memory import store

client = TestClient(app)


def seed_doc():
    doc_id = "test-doc-happy"
    # Clear any previous run
    store.documents.pop(doc_id, None)
    chunks = [
        Chunk(
            id="c1",
            section="Management Discussion",
            page_start=1,
            page_end=1,
            text=(
                "Q3 2024 revenue was $100 million. Gross margin was 42%. "
                "Operating margin reached 18%. EPS was $1.23."
            ),
        ),
        Chunk(
            id="c2",
            section="Outlook",
            page_start=2,
            page_end=2,
            text=(
                "In our outlook, we expect Q3 2024 revenue to be $100 to $120 million. "
                "We also expect free cash flow margin to be 12% to 14%."
            ),
        ),
        Chunk(
            id="c3",
            section="Capital Allocation",
            page_start=3,
            page_end=3,
            text=(
                "The Board authorized a share repurchase program of $500 million. "
                "During Q3 2024, we repurchased $200 million of shares."
            ),
        ),
    ]
    store.documents[doc_id] = {"chunks": chunks, "embeddings": []}
    return doc_id


def test_metrics_series_guidance_buybacks_happy_path():
    doc_id = seed_doc()

    # Metrics
    r = client.post("/api/metrics", json={"doc_id": doc_id})
    assert r.status_code == 200, r.text
    m = r.json().get("metrics", {})
    assert "revenue" in m
    assert m["revenue"]["unit"] in ("USD_millions", "USD")

    # Series for revenue and eps
    s = client.post("/api/series", json={"doc_id": doc_id, "metrics": ["revenue", "eps_gaap"]})
    assert s.status_code == 200, s.text
    series = s.json().get("series", {})
    # Labels/values may be minimal but should exist at least for revenue
    if "revenue" in series:
        assert len(series["revenue"].get("labels", [])) >= 1
        assert len(series["revenue"].get("values", [])) >= 1

    # Guidance (heuristic fallback will be used if no OPENAI key)
    g = client.post("/api/guidance", json={"doc_id": doc_id})
    assert g.status_code == 200, g.text
    guidance = g.json().get("guidance", [])
    assert isinstance(guidance, list)
    if guidance:
        first = guidance[0]
        assert any(k in first for k in ("value_low", "value_high", "value_point", "outlook_note"))

    # Buybacks returns a flat list
    b = client.post("/api/buybacks", json={"doc_id": doc_id})
    assert b.status_code == 200, b.text
    buybacks = b.json().get("buybacks", [])
    assert isinstance(buybacks, list)
    if buybacks:
        item = buybacks[0]
        assert any(k in item for k in ("authorization_amount", "repurchased_amount"))
