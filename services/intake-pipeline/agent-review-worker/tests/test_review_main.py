"""Smoke tests for agent-review-worker FastAPI app."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from agent_review_worker.main import app

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.lifespan_context = original_lifespan


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "agent-review-worker"
