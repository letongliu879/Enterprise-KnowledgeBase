"""Tests for parse snapshots and chunks."""

import pytest
import respx
from fastapi.testclient import TestClient

from conftest import _make_token


class TestParseSnapshots:
    def test_get_snapshot(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(
                200, json={
                    "parse_snapshot_id": "ps_123",
                    "source_file_id": "sf_123",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "parser_backend": "naive",
                    "parser_profile_id": "parser_naive_v1",
                    "input_hash": "abc123",
                    "preview_text_ref": "ref://preview",
                    "normalized_blocks_ref": "ref://blocks",
                    "outline_ref": "ref://outline",
                    "chunk_preview_ref": "ref://chunks",
                    "warnings": [],
                    "created_at": "2026-05-27T10:00:00Z",
                }
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_123",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["parse_snapshot_id"] == "ps_123"

    def test_get_snapshot_not_implemented(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(404)
            resp = client.get(
                "/workbench/parse-snapshots/ps_123",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_get_snapshot_chunks(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(
                200, json={
                    "parse_snapshot_id": "ps_123",
                    "source_file_id": "sf_123",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "parser_backend": "naive",
                    "parser_profile_id": "parser_naive_v1",
                    "input_hash": "abc123",
                    "preview_text_ref": "ref://preview",
                    "normalized_blocks_ref": "ref://blocks",
                    "outline_ref": "ref://outline",
                    "chunk_preview_ref": "ref://chunks",
                    "warnings": [],
                    "created_at": "2026-05-27T10:00:00Z",
                }
            )
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123/chunks").respond(
                200, json=[
                    {
                        "evidence_id": "ev_001",
                        "doc_id": "doc_123",
                        "content": "Chunk content",
                        "section_path": ["Section 1"],
                        "chunk_type": "text",
                    }
                ]
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_123/chunks",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["items"][0]["evidence_id"] == "ev_001"

    def test_get_snapshot_forbidden_for_other_collection(self, client: TestClient):
        other_user_token = _make_token(
            "user-999",
            "other@example.com",
            ["uploader"],
            allowed_collections=["col_other"],
        )
        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(
                200, json={
                    "parse_snapshot_id": "ps_123",
                    "source_file_id": "sf_123",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "parser_backend": "naive",
                    "parser_profile_id": "parser_naive_v1",
                    "input_hash": "abc123",
                    "preview_text_ref": "ref://preview",
                    "normalized_blocks_ref": "ref://blocks",
                    "outline_ref": "ref://outline",
                    "chunk_preview_ref": "ref://chunks",
                    "warnings": [],
                    "created_at": "2026-05-27T10:00:00Z",
                }
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_123",
                headers={"Authorization": f"Bearer {other_user_token}"},
            )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "FORBIDDEN"

    def test_get_chunk(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.get("http://localhost:8002/internal/chunks").respond(
                200, json=[
                    {
                        "evidence_id": "ev_123",
                        "doc_id": "doc_123",
                        "content": "Chunk content",
                        "section_path": ["Section 1"],
                        "chunk_type": "text",
                    }
                ]
            )
            resp = client.get(
                "/workbench/chunks/ev_123",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["evidence_id"] == "ev_123"
            assert data["content"] == "Chunk content"

    def test_chunk_wire_uses_canonical_names(self, client: TestClient, uploader_token: str):
        """Verify chunk responses use canonical wire fields, not old names."""
        with respx.mock:
            respx.get("http://localhost:8002/internal/chunks").respond(
                200, json=[
                    {
                        "evidence_id": "ev_123",
                        "doc_id": "doc_123",
                        "content": "Chunk content",
                    }
                ]
            )
            resp = client.get(
                "/workbench/chunks/ev_123",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # Must use canonical wire
            assert "evidence_id" in data
            assert "doc_id" in data
            assert "content" in data
            # Must NOT use old wire names
            assert "chunk_id" not in data
            assert "final_doc_id" not in data
            assert "display_text" not in data
