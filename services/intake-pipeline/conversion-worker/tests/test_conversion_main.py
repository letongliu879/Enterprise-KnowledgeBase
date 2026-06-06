"""Smoke tests for conversion-worker FastAPI app."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from conversion_worker.main import create_app

    with TestClient(create_app(start_background_poller=False)) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "conversion-worker"


def test_module_level_app_has_all_routes():
    """Verify that the module-level `app` object (used by uvicorn) includes
    all registered routes. This catches the module-loading-order bug where
    routes were registered after app.include_router() had already been called.
    """
    from conversion_worker.main import app

    paths = {r.path for r in app.routes}
    assert "/health" in paths, "health route missing from module-level app"
    assert "/internal/conversion/run" in paths, "conversion run route missing from module-level app"


def test_router_is_fully_populated():
    """Ensure the router itself carries all expected endpoints before inclusion."""
    from conversion_worker.routes import router

    paths = {r.path for r in router.routes}
    assert "/health" in paths
    assert "/internal/conversion/run" in paths
