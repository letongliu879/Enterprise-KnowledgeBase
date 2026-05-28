"""Tests for intake-pipeline internal owner APIs."""

import pytest
from fastapi.testclient import TestClient

from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing

from intake_pipeline.main import app


@pytest.fixture(autouse=True)
def _db():
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    yield
    drop_all()


@pytest.fixture
def client():
    return TestClient(app)


class TestRegisterSourceFile:
    def test_register_success(self, client: TestClient):
        resp = client.post(
            "/internal/source-files",
            json={
                "command_id": "cmd_001",
                "trace_id": "trc_001",
                "idempotency_key": "idem_001",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_file_id"].startswith("src_")
        assert data["state"] == "READY"
        assert data["tenant_id"] == "tenant_acme"
        assert data["collection_id"] == "col_default"

    def test_register_idempotency(self, client: TestClient):
        req = {
            "command_id": "cmd_002",
            "trace_id": "trc_002",
            "idempotency_key": "idem_002",
            "actor": "user-001",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "filename": "test.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
        }
        resp1 = client.post("/internal/source-files", json=req)
        assert resp1.status_code == 200
        source_file_id_1 = resp1.json()["source_file_id"]

        resp2 = client.post("/internal/source-files", json=req)
        assert resp2.status_code == 200
        source_file_id_2 = resp2.json()["source_file_id"]

        # Same idempotency key returns same source file
        assert source_file_id_1 == source_file_id_2

    def test_get_source_file(self, client: TestClient):
        resp = client.post(
            "/internal/source-files",
            json={
                "command_id": "cmd_003",
                "trace_id": "trc_003",
                "idempotency_key": "idem_003",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        source_file_id = resp.json()["source_file_id"]

        get_resp = client.get(f"/internal/source-files/{source_file_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["source_file_id"] == source_file_id
        assert data["state"] == "READY"

    def test_get_source_file_not_found(self, client: TestClient):
        resp = client.get("/internal/source-files/nonexistent")
        assert resp.status_code == 404

    def test_get_intake_job(self, client: TestClient):
        resp = client.post(
            "/internal/source-files",
            json={
                "command_id": "cmd_004",
                "trace_id": "trc_004",
                "idempotency_key": "idem_004",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        intake_job_id = resp.json()["intake_job_id"]

        get_resp = client.get(f"/internal/intake-jobs/{intake_job_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["intake_job_id"] == intake_job_id
        assert data["state"] == "CREATED"

    def test_get_intake_job_not_found(self, client: TestClient):
        resp = client.get("/internal/intake-jobs/nonexistent")
        assert resp.status_code == 404

    def test_get_published_document(self, client: TestClient):
        # Register a source file first
        resp = client.post(
            "/internal/source-files",
            json={
                "command_id": "cmd_005",
                "trace_id": "trc_005",
                "idempotency_key": "idem_005",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        source_file_id = resp.json()["source_file_id"]

        # Manually set published state for testing
        from intake_pipeline.main import service
        doc = service._documents[source_file_id]
        doc.publish_state = "PUBLISH_SUCCEEDED"
        doc.published_document_id = "pd_doc_test"
        doc.final_doc_id = "doc_test"

        get_resp = client.get("/internal/published-documents/pd_doc_test")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["published_document_id"] == "pd_doc_test"
        assert data["final_doc_id"] == "doc_test"
        assert data["source_file_id"] == source_file_id

    def test_get_published_document_not_found(self, client: TestClient):
        resp = client.get("/internal/published-documents/pd_nonexistent")
        assert resp.status_code == 404

    def test_register_source_file_preserves_tenant(self, client: TestClient):
        resp = client.post(
            "/internal/source-files",
            json={
                "command_id": "cmd_tenant",
                "trace_id": "trc_tenant",
                "idempotency_key": "idem_tenant",
                "actor": "user-001",
                "tenant_id": "tenant_other",
                "collection_id": "col_other",
                "filename": "other.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "tenant_other"
        assert data["collection_id"] == "col_other"

        # Verify roundtrip preserves tenant
        source_file_id = data["source_file_id"]
        get_resp = client.get(f"/internal/source-files/{source_file_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["tenant_id"] == "tenant_other"
        assert get_data["collection_id"] == "col_other"
