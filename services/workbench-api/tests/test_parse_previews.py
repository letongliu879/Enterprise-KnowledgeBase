"""Tests for parse previews."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestParsePreviews:
    def test_create_parse_preview(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.post("http://localhost:8002/internal/parse-previews").respond(
                202, json={
                    "request_id": "preview_123",
                    "trace_id": "trc_123",
                    "source_file_id": "sf_123",
                    "parser_profile_id": "parser_naive_v1",
                    "chunk_profile_id": "chunk_default",
                    "parse_mode": "standard",
                    "document_family": "pdf",
                    "decision_reason": "accepted",
                }
            )
            resp = client.post(
                "/workbench/parse-previews",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "upload_id": "upload_123",
                    "source_file_id": "sf_123",
                    "collection_id": "col_default",
                    "tenant_id": "tenant_acme",
                    "parser_profile_id": "parser_naive_v1",
                    "actor": "user-001",
                },
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "accepted"

    def test_create_parse_preview_not_implemented(self, client: TestClient, uploader_token: str):
        with respx.mock:
            respx.post("http://localhost:8002/internal/parse-previews").respond(404)
            resp = client.post(
                "/workbench/parse-previews",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "upload_id": "upload_123",
                    "source_file_id": "sf_123",
                    "collection_id": "col_default",
                    "tenant_id": "tenant_acme",
                    "parser_profile_id": "parser_naive_v1",
                    "actor": "user-001",
                },
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_create_parse_preview_unauthorized(self, client: TestClient):
        resp = client.post(
            "/workbench/parse-previews",
            json={
                "upload_id": "upload_123",
                "source_file_id": "sf_123",
                "collection_id": "col_default",
                "tenant_id": "tenant_acme",
                "parser_profile_id": "parser_naive_v1",
                "actor": "user-001",
            },
        )
        assert resp.status_code == 401

    def test_get_parse_preview(self, client: TestClient, uploader_token: str):
        resp = client.get(
            "/workbench/parse-previews/preview_123",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == "preview_123"
        assert data["status"] == "pending"
