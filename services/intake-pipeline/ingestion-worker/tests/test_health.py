"""Tests for ingestion-worker health endpoint."""

from fastapi.testclient import TestClient

from ingestion_worker.app_factory import create_app


def test_health_returns_200():
    with TestClient(
        create_app(
            include_monitor_routes=False,
            include_indexing_routes=False,
            start_background_poller=False,
        )
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ingestion-worker"
        assert "version" in data


def test_health_response_is_json():
    with TestClient(
        create_app(
            include_monitor_routes=False,
            include_indexing_routes=False,
            start_background_poller=False,
        )
    ) as client:
        resp = client.get("/health")
        assert resp.headers["content-type"] == "application/json"
