import os
import uuid
import numpy as np
import pytest

from app.db.base import init_db
from app.db.persistence import save_document, load_document, save_guidance_insights, load_guidance_insights, is_db_enabled
from app.models.types import Chunk


DB_URL = os.getenv("DATABASE_URL", "").strip()

skip_if_no_db = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set; skipping DB round-trip tests")


@skip_if_no_db
def test_document_roundtrip():
    # Ensure DB engine initialized
    init_db()
    assert is_db_enabled()

    doc_id = str(uuid.uuid4())
    chunks = [
        Chunk(id=str(uuid.uuid4()), text="Revenue was $100 million in Q3 2024.", section="MD&A", page_start=1, page_end=1)
    ]
    # Build embeddings with correct vector dimension (1536)
    embs = np.zeros((len(chunks), 1536), dtype=np.float32)

    save_document(
        doc_id=doc_id,
        filename="test.pdf",
        chunks=chunks,
        embeddings=embs,
        ticker="TEST",
        company="Test Inc.",
        source_url="https://example.com/test.pdf",
        ingest_status="test_save",
    )

    loaded = load_document(doc_id)
    assert loaded is not None
    assert len(loaded["chunks"]) == len(chunks)
    assert loaded["embeddings"].shape[0] == len(chunks)


@skip_if_no_db
def test_guidance_insights_roundtrip():
    init_db()
    assert is_db_enabled()

    doc_id = str(uuid.uuid4())
    # Save a minimal doc so FK references are valid
    chunks = [Chunk(id=str(uuid.uuid4()), text="Outlook: revenue $100 to $120 million.", section="Outlook", page_start=2, page_end=2)]
    embs = np.zeros((len(chunks), 1536), dtype=np.float32)
    save_document(doc_id, "test2.pdf", chunks, embs, ticker="TST", company="TestCo")

    # Save guidance insights
    items = [
        {
            "id": str(uuid.uuid4()),
            "metric": "revenue",
            "period": "Q3 FY24",
            "value_low": 100.0,
            "value_high": 120.0,
            "value_point": None,
            "unit": "USD_millions",
            "outlook_note": "Stable demand",
            "confidence": "medium",
            "source": "heuristic",
            "source_chunk": None,
            "citations": [],
        }
    ]
    save_guidance_insights(doc_id, items)

    rows = load_guidance_insights(doc_id)
    assert isinstance(rows, list)
    assert rows and rows[0]["metric"] == "revenue"
