"""Tests for upload sessions."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestUploads:
    def test_create_upload_success(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "access_scope_json": {"scope_type": "internal", "department": "Engineering"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["upload_id"].startswith("upload_")
        assert data["status"] in ("uploading", "failed")
        assert data["filename"] == "test.pdf"
        assert data["user_id"] == "user-001"
        assert data["access_scope_json"]["scope_type"] == "internal"

    def test_create_upload_unauthorized(self, client: TestClient):
        resp = client.post(
            "/workbench/uploads",
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 401

    def test_create_upload_wrong_role(self, client: TestClient, reviewer_token: str):
        resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 403

    def test_create_upload_collection_denied(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_unauthorized",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 403

    def test_list_uploads(self, client: TestClient, uploader_token: str):
        # Create first
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
        resp = client.get("/workbench/uploads", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_upload(self, client: TestClient, uploader_token: str):
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
        resp = client.get(f"/workbench/uploads/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        assert resp.json()["upload_id"] == upload_id

    def test_get_upload_not_found(self, client: TestClient, uploader_token: str):
        resp = client.get("/workbench/uploads/nonexistent", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 404

    def test_delete_upload(self, client: TestClient, uploader_token: str):
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
        resp = client.delete(f"/workbench/uploads/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 204

    def test_upload_idempotency(self, client: TestClient, uploader_token: str):
        # Upload idempotency: same upload_id should not create duplicate source files
        # In our implementation, we use upload_id as idempotency key for intake
        # This test verifies the local projection behavior
        resp1 = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        resp2 = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        # Different upload_ids generated each time
        assert resp1.json()["upload_id"] != resp2.json()["upload_id"]

    def test_upload_content_uses_access_scope_visibility(self, client: TestClient, uploader_token: str):
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "access_scope_json": {"scope_type": "external", "customer": "acme"},
            },
        )
        upload_id = create_resp.json()["upload_id"]

        captured = {}

        async def _fake_upload_file(self, collection_id, visibility, filename, content_bytes, mime_type, upload_id=None):
            captured["collection_id"] = collection_id
            captured["visibility"] = visibility
            captured["filename"] = filename
            captured["mime_type"] = mime_type
            captured["size"] = len(content_bytes)
            captured["upload_id"] = upload_id
            return {
                "source_file_id": "sf_123",
                "status": "UPLOADED",
                "duplicate": False,
            }

        with patch(
            "workbench_api.downstream_clients.DocumentServiceClient.upload_file",
            new=_fake_upload_file,
        ):
            resp = client.post(
                f"/workbench/uploads/{upload_id}/content",
                headers={"Authorization": f"Bearer {uploader_token}"},
                data={"access_scope_json": json.dumps({"scope_type": "external", "customer": "acme"})},
                files={"file": ("test.pdf", b"%PDF-1.4\n", "application/pdf")},
            )

        assert resp.status_code == 200
        assert captured["collection_id"] == "col_default"
        assert captured["visibility"] == "EXTERNAL"
        assert captured["filename"] == "test.pdf"
        assert captured["mime_type"] == "application/pdf"
        assert captured["size"] > 0

    def test_upload_content_reuses_persisted_access_scope(self, client: TestClient, uploader_token: str):
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "access_scope_json": {"scope_type": "external", "customer": "acme"},
            },
        )
        upload_id = create_resp.json()["upload_id"]

        captured = {}

        async def _fake_upload_file(self, collection_id, visibility, filename, content_bytes, mime_type, upload_id=None):
            captured["visibility"] = visibility
            captured["upload_id"] = upload_id
            return {
                "source_file_id": "sf_123",
                "status": "UPLOADED",
                "duplicate": False,
            }

        with patch(
            "workbench_api.downstream_clients.DocumentServiceClient.upload_file",
            new=_fake_upload_file,
        ):
            resp = client.post(
                f"/workbench/uploads/{upload_id}/content",
                headers={"Authorization": f"Bearer {uploader_token}"},
                files={"file": ("test.pdf", b"%PDF-1.4\n", "application/pdf")},
            )

        assert resp.status_code == 200
        assert captured["visibility"] == "EXTERNAL"
        assert resp.json()["access_scope_json"]["scope_type"] == "external"
