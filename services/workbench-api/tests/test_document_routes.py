"""Quick integration test to verify the document detail route works."""
import pytest
from fastapi.testclient import TestClient


def test_get_document_detail_route_exists(client: TestClient, uploader_token: str):
    """Verify GET /workbench/documents/{doc_id} returns 404 (not 405)."""
    resp = client.get(
        "/workbench/documents/doc-test-001",
        headers={"Authorization": f"Bearer {uploader_token}"},
    )
    # Should be 404 (not found) rather than 405 (method not allowed) or 501
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


def test_list_documents_route_exists(client: TestClient, uploader_token: str):
    """Verify GET /workbench/documents returns 200."""
    resp = client.get(
        "/workbench/documents",
        headers={"Authorization": f"Bearer {uploader_token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "items" in data
    assert "total" in data
