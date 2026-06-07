"""Tests for parse snapshots and chunks."""

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from conftest import _make_token
from reality_rag_persistence.models import (
    ChunkRegistryModel,
    IntakeJobModel,
    ParseSnapshotModel,
    SourceFileModel,
)


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
            assert data["items"][0]["doc_id"] == "doc_123"

    def test_get_snapshot_chunks_rewrites_source_file_doc_id_to_final_doc_id(
        self,
        client: TestClient,
        uploader_token: str,
        db_session,
    ):
        db_session.add(
            SourceFileModel(
                source_file_id="sf_123",
                upload_id="upload_123",
                object_id="obj_123",
                collection_id="col_default",
                visibility="INTERNAL",
                original_name="example.md",
                sanitized_name="example.md",
                content_hash="sha256:test",
                size_bytes=12,
                state="cleanable",
                claimed_by_job_id="job_123",
            )
        )
        db_session.add(
            IntakeJobModel(
                intake_job_id="job_123",
                source_file_id="sf_123",
                object_id="obj_123",
                collection_id="col_default",
                state="published",
                state_version=1,
                current_stage="publishing",
                preliminary_doc_id="doc_final_123",
                final_doc_id="doc_final_123",
                trace_id="trace_123",
            )
        )
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(
                200,
                json={
                    "parse_snapshot_id": "ps_123",
                    "source_file_id": "sf_123",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                },
            )
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123/chunks").respond(
                200,
                json=[
                    {
                        "evidence_id": "ev_001",
                        "doc_id": "sf_123",
                        "content": "Chunk content",
                    }
                ],
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_123/chunks",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"][0]["doc_id"] == "doc_final_123"

    def test_get_snapshot_source_blob(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_123").respond(
                200,
                json={
                    "parse_snapshot_id": "ps_123",
                    "source_file_id": "sf_123",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                },
            )
            respx.get("http://localhost:8006/internal/source-files/sf_123").respond(
                200,
                json={
                    "source_file_id": "sf_123",
                    "original_name": "example.pdf",
                    "mime_type": "application/pdf",
                    "download_url": "https://files.example.test/example.pdf",
                },
            )
            respx.get("https://files.example.test/example.pdf").mock(
                return_value=Response(
                    200,
                    content=b"%PDF-test",
                    headers={"content-type": "application/pdf"},
                )
            )

            resp = client.get(
                "/workbench/parse-snapshots/ps_123/source",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "filename=\"example.pdf\"" in resp.headers["content-disposition"]
        assert "filename*=UTF-8''example.pdf" in resp.headers["content-disposition"]
        assert resp.content == b"%PDF-test"

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

    def test_get_snapshot_uses_local_fallback_when_indexing_unavailable(
        self,
        client: TestClient,
        uploader_token: str,
        db_session,
        tmp_path: Path,
    ):
        db_session.add(
            SourceFileModel(
                source_file_id="sf_local",
                upload_id="upload_local",
                object_id="obj_local",
                collection_id="col_default",
                visibility="INTERNAL",
                original_name="example.txt",
                sanitized_name="example.txt",
                content_hash="sha256:x",
                size_bytes=5,
                state="cleanable",
                claimed_by_job_id="job_local",
            )
        )
        db_session.add(
            IntakeJobModel(
                intake_job_id="job_local",
                source_file_id="sf_local",
                object_id="obj_local",
                collection_id="col_default",
                state="published",
                state_version=1,
                current_stage="publishing",
                preliminary_doc_id="doc_local",
                final_doc_id="doc_local",
                trace_id="trace_local",
            )
        )
        db_session.add(
            ParseSnapshotModel(
                parse_snapshot_id="ps_local",
                request_id="req_local",
                tenant_id="tenant_acme",
                collection_id="col_default",
                source_file_id="sf_local",
                source_binary_ref=str(tmp_path / "example.txt"),
                source_filename="example.txt",
                source_suffix="txt",
                parser_id="naive",
                parser_backend="ragflow_app",
                input_hash="sha256:x",
                preview_text="hello",
            )
        )
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_local").mock(
                side_effect=httpx.ConnectError("boom")
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_local",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["parse_snapshot_id"] == "ps_local"
        assert data["source_file_id"] == "sf_local"

    def test_get_snapshot_chunks_uses_local_fallback_when_indexing_unavailable(
        self,
        client: TestClient,
        uploader_token: str,
        db_session,
        tmp_path: Path,
    ):
        db_session.add(
            SourceFileModel(
                source_file_id="sf_local_chunks",
                upload_id="upload_local_chunks",
                object_id="obj_local_chunks",
                collection_id="col_default",
                visibility="INTERNAL",
                original_name="example.txt",
                sanitized_name="example.txt",
                content_hash="sha256:y",
                size_bytes=5,
                state="cleanable",
                claimed_by_job_id="job_local_chunks",
            )
        )
        db_session.add(
            IntakeJobModel(
                intake_job_id="job_local_chunks",
                source_file_id="sf_local_chunks",
                object_id="obj_local_chunks",
                collection_id="col_default",
                state="published",
                state_version=1,
                current_stage="publishing",
                preliminary_doc_id="doc_local_chunks",
                final_doc_id="doc_local_chunks",
                trace_id="trace_local_chunks",
            )
        )
        db_session.add(
            ParseSnapshotModel(
                parse_snapshot_id="ps_local_chunks",
                request_id="req_local_chunks",
                tenant_id="tenant_acme",
                collection_id="col_default",
                source_file_id="sf_local_chunks",
                source_binary_ref=str(tmp_path / "example.txt"),
                source_filename="example.txt",
                source_suffix="txt",
                parser_id="naive",
                parser_backend="ragflow_app",
                input_hash="sha256:y",
                preview_text="hello",
            )
        )
        db_session.add(
            ChunkRegistryModel(
                chunk_id="chk_local_001",
                tenant_id="tenant_acme",
                collection_id="col_default",
                final_doc_id="doc_local_chunks",
                index_version_id="v1",
                available_int=1,
                visibility="INTERNAL",
                payload_json={
                    "chunk_id": "chk_local_001",
                    "final_doc_id": "doc_local_chunks",
                    "display_text": "Chunk content",
                    "section_path": ["Section 1"],
                    "page_spans": [{"page_from": 1, "page_to": 1}],
                    "metadata": {"k": "v"},
                },
            )
        )
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_local_chunks").mock(
                side_effect=httpx.ConnectError("boom")
            )
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_local_chunks/chunks").mock(
                side_effect=httpx.ConnectError("boom")
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_local_chunks/chunks",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["evidence_id"] == "chk_local_001"
        assert data["items"][0]["doc_id"] == "doc_local_chunks"
        assert data["items"][0]["content"] == "Chunk content"

    def test_get_snapshot_source_uses_local_file_when_intake_unavailable(
        self,
        client: TestClient,
        uploader_token: str,
        db_session,
        tmp_path: Path,
    ):
        source_path = tmp_path / "example.txt"
        source_path.write_text("local source", encoding="utf-8")

        db_session.add(
            SourceFileModel(
                source_file_id="sf_local_source",
                upload_id="upload_local_source",
                object_id="obj_local_source",
                collection_id="col_default",
                visibility="INTERNAL",
                original_name="example.txt",
                sanitized_name="example.txt",
                content_hash="sha256:z",
                size_bytes=12,
                state="cleanable",
                claimed_by_job_id="job_local_source",
            )
        )
        db_session.add(
            IntakeJobModel(
                intake_job_id="job_local_source",
                source_file_id="sf_local_source",
                object_id="obj_local_source",
                collection_id="col_default",
                state="published",
                state_version=1,
                current_stage="publishing",
                preliminary_doc_id="doc_local_source",
                final_doc_id="doc_local_source",
                trace_id="trace_local_source",
            )
        )
        db_session.add(
            ParseSnapshotModel(
                parse_snapshot_id="ps_local_source",
                request_id="req_local_source",
                tenant_id="tenant_acme",
                collection_id="col_default",
                source_file_id="sf_local_source",
                source_binary_ref=str(source_path),
                source_filename="example.txt",
                source_suffix="txt",
                parser_id="naive",
                parser_backend="ragflow_app",
                input_hash="sha256:z",
                preview_text="local source",
            )
        )
        db_session.commit()

        with respx.mock:
            respx.get("http://localhost:8002/internal/parse-snapshots/ps_local_source").mock(
                side_effect=httpx.ConnectError("boom")
            )
            respx.get("http://localhost:8006/internal/source-files/sf_local_source").mock(
                side_effect=httpx.ConnectError("boom")
            )
            resp = client.get(
                "/workbench/parse-snapshots/ps_local_source/source",
                headers={"Authorization": f"Bearer {uploader_token}"},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "filename*=UTF-8''example.txt" in resp.headers["content-disposition"]
        assert resp.content == b"local source"
