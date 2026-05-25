"""Smoke tests for indexing-service FastAPI app."""

from fastapi.testclient import TestClient

from indexing_service.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "indexing-service"
