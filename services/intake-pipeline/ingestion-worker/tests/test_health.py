"""Tests for ingestion-worker health endpoint."""

from fastapi.testclient import TestClient

from ingestion_worker.main import app

client = TestClient(app)


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "ingestion-worker"
    assert "version" in data


def test_health_response_is_json():
    resp = client.get("/health")
    assert resp.headers["content-type"] == "application/json"
