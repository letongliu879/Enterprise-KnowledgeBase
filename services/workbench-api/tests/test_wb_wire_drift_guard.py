"""Drift guard: verify no old wire fields in workbench responses."""

import pytest
from fastapi.testclient import TestClient


OLD_WIRE_FIELDS = ["query_text", "max_context_tokens", "result_chunks", "final_doc_id", "chunk_id", "display_text"]


class TestWireDriftGuard:
    def test_no_old_wire_in_chunk_edits(self, client: TestClient, chunk_editor_token: str):
        resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Test content",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        for old_field in OLD_WIRE_FIELDS:
            assert old_field not in data, f"Old wire field '{old_field}' found in chunk edit response"

    def test_no_old_wire_in_uploads(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        for old_field in OLD_WIRE_FIELDS:
            assert old_field not in data, f"Old wire field '{old_field}' found in upload response"

    def test_canonical_wire_present(self, client: TestClient, chunk_editor_token: str):
        resp = client.post(
            "/workbench/parse-snapshots/ps_123/chunk-edits",
            headers={"Authorization": f"Bearer {chunk_editor_token}"},
            json={
                "base_evidence_id": "ev_001",
                "operation": "update",
                "content": "Test content",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "base_evidence_id" in data
        assert "content" in data
