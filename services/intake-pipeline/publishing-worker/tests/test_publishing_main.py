"""Smoke tests for publishing-worker FastAPI app."""

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from publishing_worker.main import app
    return TestClient(app)


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "publishing-worker"
