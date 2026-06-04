"""Guardrails for the compatibility-root intake API."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _load_local_compat_root():
    module_path = Path(__file__).resolve().parents[2] / "src" / "intake_pipeline" / "main.py"
    module_name = f"intake_pipeline_compat_root_{uuid4().hex}"
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load compat root from {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_compat_root_write_endpoints_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("REALITY_RAG_ENABLE_COMPAT_WRITES", raising=False)
    monkeypatch.delenv("ALLOW_LOCAL_FALLBACK_FOR_TESTS", raising=False)
    monkeypatch.delenv("REALITY_RAG_INDEXING_BASE_URL", raising=False)

    with TestClient(_load_local_compat_root()) as client:
        response = client.post(
            "/v1/documents",
            json={
                "tenant_id": "tenant-1",
                "collection_id": "col-1",
                "filename": "policy.md",
                "content_text": "hello",
            },
        )

    assert response.status_code == 503
    assert "disabled by default" in response.json()["detail"].lower()


def test_compat_root_requires_explicit_indexing_url_when_writes_are_enabled(monkeypatch):
    monkeypatch.setenv("REALITY_RAG_ENABLE_COMPAT_WRITES", "true")
    monkeypatch.delenv("ALLOW_LOCAL_FALLBACK_FOR_TESTS", raising=False)
    monkeypatch.delenv("REALITY_RAG_INDEXING_BASE_URL", raising=False)

    with TestClient(_load_local_compat_root()) as client:
        response = client.post(
            "/v1/documents",
            json={
                "tenant_id": "tenant-1",
                "collection_id": "col-1",
                "filename": "policy.md",
                "content_text": "hello",
            },
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "REALITY_RAG_INDEXING_BASE_URL" in detail
    assert "ALLOW_LOCAL_FALLBACK_FOR_TESTS=true" in detail
