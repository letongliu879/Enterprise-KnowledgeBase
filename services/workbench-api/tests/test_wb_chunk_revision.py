"""Tests for chunk revision (post-publish)."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestChunkRevision:
    def test_patch_chunk_requires_editor(self, client: TestClient, uploader_token: str):
        resp = client.patch(
            "/workbench/chunks/ev_001",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "command_id": "cmd_001",
                "trace_id": "trc_001",
                "idempotency_key": "ce_001",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "target_type": "chunk",
                "target_id": "ev_001",
                "payload": {
                    "evidence_id": "ev_001",
                    "doc_id": "doc_001",
                    "operation": "update",
                },
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "FORBIDDEN"

    def test_patch_chunk_downstream_not_implemented(self, client: TestClient, chunk_editor_token: str):
        with respx.mock:
            respx.post("http://localhost:8002/internal/chunks/ev_001/revisions").respond(404)
            resp = client.patch(
                "/workbench/chunks/ev_001",
                headers={"Authorization": f"Bearer {chunk_editor_token}"},
                json={
                    "command_id": "cmd_001",
                    "trace_id": "trc_001",
                    "idempotency_key": "ce_001",
                    "actor": "user-002",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "target_type": "chunk",
                    "target_id": "ev_001",
                    "payload": {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_001",
                        "operation": "update",
                        "content": "Updated content",
                    },
                },
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_patch_chunk_success(self, client: TestClient, chunk_editor_token: str):
        with respx.mock:
            respx.post("http://localhost:8002/internal/chunks/ev_001/revisions").respond(
                202, json={"revision_id": "rev_001", "status": "accepted"}
            )
            resp = client.patch(
                "/workbench/chunks/ev_001",
                headers={"Authorization": f"Bearer {chunk_editor_token}"},
                json={
                    "command_id": "cmd_001",
                    "trace_id": "trc_001",
                    "idempotency_key": "ce_001",
                    "actor": "user-002",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "target_type": "chunk",
                    "target_id": "ev_001",
                    "payload": {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_001",
                        "operation": "update",
                        "content": "Updated content",
                    },
                },
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["revision_id"] == "rev_001"
            assert data["status"] == "accepted"

    def test_chunk_revision_idempotency(self, client: TestClient, chunk_editor_token: str):
        # Idempotency key must be stable (chunk_edit_id)
        with respx.mock:
            respx.post("http://localhost:8002/internal/chunks/ev_001/revisions").respond(404)
            resp = client.patch(
                "/workbench/chunks/ev_001",
                headers={"Authorization": f"Bearer {chunk_editor_token}"},
                json={
                    "command_id": "cmd_001",
                    "trace_id": "trc_001",
                    "idempotency_key": "ce_001",  # stable idempotency key
                    "actor": "user-002",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "target_type": "chunk",
                    "target_id": "ev_001",
                    "payload": {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_001",
                        "operation": "update",
                    },
                },
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"
