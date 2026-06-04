"""Smoke tests for publishing-worker FastAPI app."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from publishing_worker.main import create_app

    with TestClient(create_app(start_background_poller=False)) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "publishing-worker"
