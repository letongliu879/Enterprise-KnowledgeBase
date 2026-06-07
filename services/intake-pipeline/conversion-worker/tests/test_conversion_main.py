"""Smoke tests for conversion-worker FastAPI app."""

from pathlib import Path

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
    assert "/internal/source-previews/render" in paths, "source preview render route missing from module-level app"


def test_router_is_fully_populated():
    """Ensure the router itself carries all expected endpoints before inclusion."""
    from conversion_worker.routes import router

    paths = {r.path for r in router.routes}
    assert "/health" in paths
    assert "/internal/conversion/run" in paths
    assert "/internal/source-previews/render" in paths
    assert "/internal/source-previews/{source_file_id}/content" in paths


def test_render_source_preview_uses_cache(client: TestClient, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("REALITY_RAG_INTAKE_RUNTIME_DIR", str(tmp_path))

    source_path = tmp_path / "slides.pptx"
    source_path.write_bytes(b"pptx bytes")

    def fake_run(script: str, *, timeout_seconds: int = 180) -> None:
        assert "PowerPoint.Application" in script
        preview_path = tmp_path / "source-preview" / "src-preview-1" / "preview.pdf"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(b"%PDF-1.4 fake preview")

    monkeypatch.setattr("conversion_worker.source_preview._run_powershell", fake_run)

    response = client.post(
        "/internal/source-previews/render",
        json={
            "source_file_id": "src-preview-1",
            "collection_id": "col_policy",
            "source_file_path": str(source_path),
            "filename": "slides.pptx",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_available"] is True
    assert payload["preview_status"] == "ready"
    assert payload["preview_kind"] == "pdf"
    assert payload["preview_url"] == "/internal/source-previews/src-preview-1/content"

    cached = client.post(
        "/internal/source-previews/render",
        json={
            "source_file_id": "src-preview-1",
            "collection_id": "col_policy",
            "source_file_path": str(source_path),
            "filename": "slides.pptx",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        },
    )

    assert cached.status_code == 200
    assert cached.json()["preview_status"] == "ready"


def test_render_source_preview_returns_unsupported_for_native_unknown(client: TestClient, tmp_path: Path):
    source_path = tmp_path / "archive.zip"
    source_path.write_bytes(b"zip bytes")

    response = client.post(
        "/internal/source-previews/render",
        json={
            "source_file_id": "src-preview-zip",
            "collection_id": "col_policy",
            "source_file_path": str(source_path),
            "filename": "archive.zip",
            "mime_type": "application/zip",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_available"] is False
    assert payload["preview_status"] == "unsupported"
    assert payload["preview_url"] is None
