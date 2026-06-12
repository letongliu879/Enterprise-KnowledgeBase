"""Tests for document share endpoint."""

from fastapi.testclient import TestClient


def test_share_document_not_found(client: TestClient, uploader_token: str):
    """POST /workbench/documents/{doc_id}/share returns 404 for unknown doc."""
    resp = client.post(
        "/workbench/documents/doc-nonexistent/share",
        headers={"Authorization": f"Bearer {uploader_token}"},
        json={"expires_in_hours": 24, "password": None},
    )
    assert resp.status_code == 404


def test_share_document(
    client: TestClient,
    uploader_token: str,
    db_session,
):
    """POST /workbench/documents/{doc_id}/share returns share URL and expiry."""
    from reality_rag_persistence.models import WorkbenchDocumentProjectionModel
    from datetime import datetime, timezone

    doc_id = "doc-share-001"
    proj = WorkbenchDocumentProjectionModel(
        doc_id=doc_id,
        tenant_id="tenant_acme",
        collection_id="col_default",
        filename="test.pdf",
        mime_type="application/pdf",
    )
    db_session.add(proj)
    db_session.commit()

    resp = client.post(
        f"/workbench/documents/{doc_id}/share",
        headers={"Authorization": f"Bearer {uploader_token}"},
        json={"expires_in_hours": 168, "password": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_url" in data
    assert data["share_url"].startswith("http")
    assert "expires_at" in data
    assert "/share/" in data["share_url"]
