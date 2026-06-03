"""Smoke tests for indexing-service FastAPI app."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from indexing_service.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "indexing-service"
