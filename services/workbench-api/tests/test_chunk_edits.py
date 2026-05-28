"""Tests for chunk edits."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestChunkEdits:
    def test_create_chunk_edit(self, client: TestClient, chunk_editor_token: str):
        resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Updated content",
                "edit_reason": "Fix typo",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["chunk_edit_id"].startswith("ce_")
        assert data["base_evidence_id"] == "ev_001"
        assert data["content"] == "Updated content"
        assert data["operation"] == "update"
        assert data["edit_scope"] == "pre_publish"
        assert data["status"] == "draft"

    def test_create_chunk_edit_requires_editor(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
            },
        )
        assert resp.status_code == 403

    def test_list_chunk_edits(self, client: TestClient, chunk_editor_token: str):
        client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Updated content",
            },
        )
        resp = client.get(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_update_chunk_edit(self, client: TestClient, chunk_editor_token: str):
        create_resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Original",
            },
        )
        edit_id = create_resp.json()["chunk_edit_id"]
        resp = client.put(
            f"/workbench/chunk-edits/{edit_id}",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={"content": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated"

    def test_delete_chunk_edit(self, client: TestClient, chunk_editor_token: str):
        create_resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
            },
        )
        edit_id = create_resp.json()["chunk_edit_id"]
        resp = client.delete(
            f"/workbench/chunk-edits/{edit_id}",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
        )
        assert resp.status_code == 204

    def test_submit_chunk_edit_success(self, client: TestClient, chunk_editor_token: str):
        create_resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Updated content",
            },
        )
        edit_id = create_resp.json()["chunk_edit_id"]
        with respx.mock:
            respx.post("http://localhost:8002/internal/chunks/ev_001/revisions").respond(
                200, json={"revision_id": "rev_001", "status": "draft"}
            )
            resp = client.post(
                f"/workbench/chunk-edits/{edit_id}/submit",
                headers={"Authorization": f"Bearer {chunk_editor_token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["downstream_revision_id"] == "rev_001"

    def test_submit_chunk_edit_requires_editor(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/chunk-edits/ce_nonexistent/submit",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 403

    def test_submit_chunk_edit_downstream_failure(self, client: TestClient, chunk_editor_token: str):
        create_resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Updated content",
            },
        )
        edit_id = create_resp.json()["chunk_edit_id"]
        with respx.mock:
            respx.post("http://localhost:8002/internal/chunks/ev_001/revisions").respond(500, text="Internal error")
            resp = client.post(
                f"/workbench/chunk-edits/{edit_id}/submit",
                headers={"Authorization": f"Bearer {chunk_editor_token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "CONFLICT"
