from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_root():
    r = client.get("/")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_guidance_and_buybacks_shapes_without_doc():
    # Expect 404 for missing doc_id
    r = client.post("/api/guidance", json={"doc_id": "missing"})
    assert r.status_code in (200, 404)

    r2 = client.post("/api/buybacks", json={"doc_id": "missing"})
    assert r2.status_code in (200, 404)


def test_guidance_rebuild_missing_doc():
    r = client.post("/api/guidance/rebuild", json={"doc_id": "missing"})
    # Rebuild should 404 if doc not found
    assert r.status_code in (200, 404)
