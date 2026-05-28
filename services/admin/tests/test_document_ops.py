"""Tests for admin document lifecycle operations."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_publishing_worker(monkeypatch):
    """Mock publishing worker client responses."""
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def archive_document(self, final_doc_id, *, actor_id="system", reason="", idempotency_key=""):
            return {
                "success": True,
                "final_doc_id": final_doc_id,
                "previous_state": "PUBLISHED",
                "new_state": "ARCHIVED",
            }

        async def retract_document(self, final_doc_id, *, actor_id="system", reason="", idempotency_key=""):
            return {
                "success": True,
                "final_doc_id": final_doc_id,
                "previous_state": "PUBLISHED",
                "new_state": "RETRACTED",
            }

    monkeypatch.setattr(
        "admin_service.document_ops.routes.PublishingWorkerClient",
        MockClient,
    )
    return MockClient


@pytest.fixture
def mock_indexing_client(monkeypatch):
    """Mock indexing client responses."""
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get_parse_snapshot(self, parse_snapshot_id):
            return {
                "parse_snapshot_id": parse_snapshot_id,
                "source_file_id": "sf_001",
                "source_binary_ref": "s3://bucket/file.pdf",
                "source_filename": "file.pdf",
                "tenant_id": "tenant_1",
                "collection_id": "coll_1",
            }

        async def submit_index_job(self, command):
            return {
                "build_job_id": "ibj_test_001",
                "status": "ACCEPTED",
            }

        async def get_index_job(self, job_id):
            return {
                "build_job_id": job_id,
                "status": "READY",
                "index_version_id": "idxv_coll_1_active",
            }

    monkeypatch.setattr(
        "admin_service.document_ops.routes.IndexingClient",
        MockClient,
    )
    return MockClient


def test_archive_document_success(client, knowledge_admin_token, mock_publishing_worker):
    resp = client.post(
        "/admin/documents/doc_001/archive",
        json={"reason": "End of life"},
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["final_doc_id"] == "doc_001"
    assert data["new_state"] == "ARCHIVED"


def test_retract_document_success(client, knowledge_admin_token, mock_publishing_worker):
    resp = client.post(
        "/admin/documents/doc_001/retract",
        json={"reason": "Sensitive content"},
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["final_doc_id"] == "doc_001"
    assert data["new_state"] == "RETRACTED"


def test_reindex_document_success(client, knowledge_admin_token, mock_indexing_client):
    resp = client.post(
        "/admin/documents/doc_001/reindex",
        json={
            "collection_id": "coll_1",
            "tenant_id": "tenant_1",
            "parse_snapshot_id": "ps_001",
            "reason": "Profile updated",
        },
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["final_doc_id"] == "doc_001"
    assert data["new_state"] == "REINDEXING"
    assert data["job_id"] == "ibj_test_001"


def test_archive_requires_admin_role(client, viewer_token, mock_publishing_worker):
    resp = client.post(
        "/admin/documents/doc_001/archive",
        json={"reason": "End of life"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_retract_requires_admin_role(client, viewer_token, mock_publishing_worker):
    resp = client.post(
        "/admin/documents/doc_001/retract",
        json={"reason": "Sensitive content"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_reindex_requires_admin_role(client, viewer_token, mock_indexing_client):
    resp = client.post(
        "/admin/documents/doc_001/reindex",
        json={
            "collection_id": "coll_1",
            "tenant_id": "tenant_1",
            "parse_snapshot_id": "ps_001",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_archive_publishing_worker_not_found(client, knowledge_admin_token, monkeypatch):
    from admin_service.downstream_clients.errors import DownstreamError

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def archive_document(self, *args, **kwargs):
            raise DownstreamError("NOT_FOUND", "Document not found", 404)

    monkeypatch.setattr(
        "admin_service.document_ops.routes.PublishingWorkerClient",
        FailingClient,
    )

    resp = client.post(
        "/admin/documents/doc_999/archive",
        json={"reason": "End of life"},
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 404


def test_reindex_snapshot_not_found(client, knowledge_admin_token, monkeypatch):
    from admin_service.downstream_clients.errors import DownstreamError

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get_parse_snapshot(self, *args, **kwargs):
            raise DownstreamError("NOT_FOUND", "Snapshot not found", 404)

        async def submit_index_job(self, *args, **kwargs):
            return {"build_job_id": "ibj_test"}

    monkeypatch.setattr(
        "admin_service.document_ops.routes.IndexingClient",
        FailingClient,
    )

    resp = client.post(
        "/admin/documents/doc_001/reindex",
        json={
            "collection_id": "coll_1",
            "tenant_id": "tenant_1",
            "parse_snapshot_id": "ps_missing",
        },
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 404


def test_archive_idempotency_logged(client, knowledge_admin_token, mock_publishing_worker, db_session):
    """Verify ops audit log is written on successful archive."""
    resp = client.post(
        "/admin/documents/doc_001/archive",
        json={
            "reason": "End of life",
            "idempotency_key": "archive:doc_001:test",
        },
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 200

    from reality_rag_persistence.repositories import OpsAuditLogRepository
    repo = OpsAuditLogRepository(db_session)
    entries = repo.list_all(target_type="document", target_id="doc_001")
    archive_entries = [e for e in entries if e.action == "archive"]
    assert len(archive_entries) >= 1
    entry = archive_entries[-1]
    assert entry.idempotency_key == "archive:doc_001:test"
    assert entry.after_state == "ARCHIVED"


def test_retract_idempotency_logged(client, knowledge_admin_token, mock_publishing_worker, db_session):
    """Verify ops audit log is written on successful retract."""
    resp = client.post(
        "/admin/documents/doc_001/retract",
        json={
            "reason": "Sensitive content",
            "idempotency_key": "retract:doc_001:test",
        },
        headers={"Authorization": f"Bearer {knowledge_admin_token}"},
    )
    assert resp.status_code == 200

    from reality_rag_persistence.repositories import OpsAuditLogRepository
    repo = OpsAuditLogRepository(db_session)
    entries = repo.list_all(target_type="document", target_id="doc_001")
    retract_entries = [e for e in entries if e.action == "retract"]
    assert len(retract_entries) >= 1
    entry = retract_entries[-1]
    assert entry.idempotency_key == "retract:doc_001:test"
    assert entry.after_state == "RETRACTED"
