"""Tests for task projection."""

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from conftest import _make_token


class TestTaskProjection:
    def test_list_tasks(self, client: TestClient, uploader_token: str):
        # Create an upload first
        client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        resp = client.get("/workbench/tasks", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_task(self, client: TestClient, uploader_token: str):
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]
        resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_id"] == upload_id
        assert "status" in data
        assert "progress_pct" in data

    def test_task_status_derived(self, client: TestClient, uploader_token: str):
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]
        resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        data = resp.json()
        # Status should be derived from owner states, not a manually set success state
        assert data["status"] in ("uploading", "parsing", "reviewing", "approved", "rejected", "published", "failed")

    def test_task_status_indexing(self, client: TestClient, uploader_token: str, db_session):
        """Test that index_build_state=BUILDING derives status='indexing'."""
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        # Set source_file_id so downstream queries are triggered
        from reality_rag_persistence.models import WorkbenchUploadSessionModel
        db_session.query(WorkbenchUploadSessionModel).filter_by(upload_id=upload_id).update({"source_file_id": "sf_001"})
        db_session.commit()

        with respx.mock:
            # Mock intake endpoints
            respx.get("http://localhost:8003/internal/source-files/sf_001").mock(
                return_value=Response(200, json={"state": "READY", "source_file_id": "sf_001", "intake_job_id": "ij_001"})
            )
            respx.get("http://localhost:8003/internal/intake-jobs/ij_001").mock(
                return_value=Response(200, json={"state": "PUBLISHED", "intake_job_id": "ij_001", "final_doc_id": "doc_001", "parse_snapshot_id": "ps_001"})
            )
            # Mock indexing endpoint
            respx.get("http://localhost:8002/internal/indexed-documents").mock(
                return_value=Response(200, json=[
                    {
                        "final_doc_id": "doc_001",
                        "index_version": "idxv_001",
                        "state": "CANDIDATE",
                        "collection_id": "col_default",
                    }
                ])
            )

            resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
            data = resp.json()
            assert data["index_build_state"] == "BUILDING"
            assert data["active_index_version"] is None
            assert data["status"] == "indexing"

    def test_task_status_published_with_index(self, client: TestClient, uploader_token: str, db_session):
        """Test that active_index_version present derives status='published'."""
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        from reality_rag_persistence.models import WorkbenchUploadSessionModel
        db_session.query(WorkbenchUploadSessionModel).filter_by(upload_id=upload_id).update({"source_file_id": "sf_001"})
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8003/internal/source-files/sf_001").mock(
                return_value=Response(200, json={"state": "READY", "source_file_id": "sf_001", "intake_job_id": "ij_001"})
            )
            respx.get("http://localhost:8003/internal/intake-jobs/ij_001").mock(
                return_value=Response(200, json={"state": "PUBLISHED", "intake_job_id": "ij_001", "final_doc_id": "doc_001", "parse_snapshot_id": "ps_001"})
            )
            respx.get("http://localhost:8002/internal/indexed-documents").mock(
                return_value=Response(200, json=[
                    {
                        "final_doc_id": "doc_001",
                        "index_version": "idxv_001",
                        "state": "ACTIVE",
                        "collection_id": "col_default",
                    }
                ])
            )

            resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
            data = resp.json()
            assert data["index_build_state"] == "ACTIVE"
            assert data["active_index_version"] == "idxv_001"
            assert data["status"] == "published"

    def test_task_status_archived(self, client: TestClient, uploader_token: str, db_session):
        """Test that published_document_state=ARCHIVED derives status='archived'."""
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        from reality_rag_persistence.models import WorkbenchUploadSessionModel
        db_session.query(WorkbenchUploadSessionModel).filter_by(upload_id=upload_id).update({"source_file_id": "sf_001"})
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8003/internal/source-files/sf_001").mock(
                return_value=Response(200, json={"state": "READY", "source_file_id": "sf_001", "intake_job_id": "ij_001"})
            )
            respx.get("http://localhost:8003/internal/intake-jobs/ij_001").mock(
                return_value=Response(200, json={
                    "state": "PUBLISHED",
                    "intake_job_id": "ij_001",
                    "final_doc_id": "doc_001",
                    "published_document_id": "pd_001",
                })
            )
            respx.get("http://localhost:8003/internal/published-documents/pd_001").mock(
                return_value=Response(200, json={"state": "ARCHIVED", "published_document_id": "pd_001"})
            )
            # Also mock indexing call (queried for all uploads with final_doc_id)
            respx.get("http://localhost:8002/internal/indexed-documents").mock(
                return_value=Response(200, json=[])
            )

            resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
            data = resp.json()
            assert data["published_document_state"] == "ARCHIVED"
            assert data["status"] == "archived"

    def test_task_status_retracted(self, client: TestClient, uploader_token: str, db_session):
        """Test that published_document_state=RETRACTED derives status='retracted'."""
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        from reality_rag_persistence.models import WorkbenchUploadSessionModel
        db_session.query(WorkbenchUploadSessionModel).filter_by(upload_id=upload_id).update({"source_file_id": "sf_001"})
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8003/internal/source-files/sf_001").mock(
                return_value=Response(200, json={"state": "READY", "source_file_id": "sf_001", "intake_job_id": "ij_001"})
            )
            respx.get("http://localhost:8003/internal/intake-jobs/ij_001").mock(
                return_value=Response(200, json={
                    "state": "PUBLISHED",
                    "intake_job_id": "ij_001",
                    "final_doc_id": "doc_001",
                    "published_document_id": "pd_001",
                })
            )
            respx.get("http://localhost:8003/internal/published-documents/pd_001").mock(
                return_value=Response(200, json={"state": "RETRACTED", "published_document_id": "pd_001"})
            )
            # Also mock indexing call (queried for all uploads with final_doc_id)
            respx.get("http://localhost:8002/internal/indexed-documents").mock(
                return_value=Response(200, json=[])
            )

            resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
            data = resp.json()
            assert data["published_document_state"] == "RETRACTED"
            assert data["status"] == "retracted"


class TestTaskProjectionTenantIsolation:
    def test_list_tasks_filtered_by_tenant(self, client: TestClient, uploader_token: str):
        # Create upload for tenant_acme
        client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "tenant_acme.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )

        # Create token for different tenant
        other_tenant_token = _make_token("user-001", "uploader@example.com", ["uploader"], tenant_id="tenant_other")

        # Other tenant should not see tenant_acme's tasks
        resp = client.get("/workbench/tasks", headers={"Authorization": f"Bearer {other_tenant_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_get_task_cross_tenant_denied(self, client: TestClient, uploader_token: str):
        # Create upload for tenant_acme
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        # Different user trying to access the task
        other_user_token = _make_token("user-999", "other@example.com", ["uploader"], tenant_id="tenant_acme")
        resp = client.get(
            f"/workbench/tasks/{upload_id}",
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        assert resp.status_code == 404
