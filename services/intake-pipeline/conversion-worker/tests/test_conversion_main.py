"""Smoke tests for conversion-worker FastAPI app."""

from fastapi.testclient import TestClient

from conversion_worker.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "conversion-worker"
