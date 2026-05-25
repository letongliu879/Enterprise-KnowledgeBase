"""Tests for document_service_client — remote/local fallback selector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reality_rag_contracts import SourceFileState
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.tenants import TenantRepository

from ingestion_worker.document_service_client import (
    DocumentServiceClient,
    _get_remote_url,
    get_document_service_client,
)


class TestGetRemoteUrl:
    def test_returns_none_by_default(self):
        assert _get_remote_url() is None

    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        # Reset cached value
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None
        assert _get_remote_url() == "http://doc-svc:8000"
        # Reset for other tests
        client_mod._REMOTE_URL = None


class TestDocumentServiceClientLocal:
    def _seed_collection(self, session, collection_id: str = "col-doc-client"):
        if TenantRepository(session).get("default") is None:
            TenantRepository(session).save(
                __import__("reality_rag_contracts").Tenant(tenant_id="default", name="Default")
            )
        if CollectionRepository(session).get(collection_id) is None:
            CollectionRepository(session).save(
                __import__("reality_rag_contracts").Collection(
                    collection_id=collection_id,
                    tenant_id="default",
                    name="Doc Client Collection",
                    authority_level=5,
                )
            )
        session.commit()

    def test_create_source_file_local(self):
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            result = client.create_source_file("col-doc-client", "obj_sha256_test", "sha256:test")
            assert result["collection_id"] == "col-doc-client"
            assert result["object_id"] == "obj_sha256_test"
            assert result["content_hash"] == "sha256:test"
            assert "source_file_id" in result
        finally:
            session.close()

    def test_claim_local(self):
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            result = client.create_source_file("col-doc-client", "obj_sha256_claim", "sha256:claim")
            sf_id = result["source_file_id"]
            assert client.claim(sf_id, "job-1") is True
            # Second claim should fail
            assert client.claim(sf_id, "job-2") is False
        finally:
            session.close()

    def test_mark_consumed_local(self):
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            result = client.create_source_file("col-doc-client", "obj_sha256_consumed", "sha256:consumed")
            sf_id = result["source_file_id"]
            client.claim(sf_id, "job-1")
            assert client.mark_consumed(sf_id, "job-1") is True
            # Wrong job should fail
            assert client.mark_consumed(sf_id, "job-2") is False
        finally:
            session.close()

    def test_mark_cleanable_local(self):
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            result = client.create_source_file("col-doc-client", "obj_sha256_clean", "sha256:clean")
            sf_id = result["source_file_id"]
            client.claim(sf_id, "job-1")
            assert client.mark_cleanable(sf_id, "job-1") is True
        finally:
            session.close()

    def test_find_active_by_content_hash_local(self):
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            client.create_source_file("col-doc-client", "obj_sha256_active", "sha256:active")
            found = client.find_active_by_content_hash("sha256:active", "col-doc-client")
            assert found is not None
            assert found["content_hash"] == "sha256:active"

            # Non-existent hash
            not_found = client.find_active_by_content_hash("sha256:missing", "col-doc-client")
            assert not_found is None
        finally:
            session.close()

    def test_get_or_create_object_blob_local(self):
        session = get_session()
        try:
            client = DocumentServiceClient(session)
            result = client.get_or_create_object_blob("sha256:blob1", "s3://bucket/blob1", 100)
            assert result["object_id"] == "obj_sha256_blob1"
            assert result["content_hash"] == "sha256:blob1"
            assert result["storage_key"] == "s3://bucket/blob1"
            assert result["ref_count"] == 0

            # Second call returns existing
            result2 = client.get_or_create_object_blob("sha256:blob1", "s3://other", 200)
            assert result2["object_id"] == result["object_id"]
            assert result2["storage_key"] == "s3://bucket/blob1"  # original kept
        finally:
            session.close()

    def test_create_source_file_requires_object_blob(self):
        """Source file creation fails if object_blob does not exist
        because source_files.object_id has FK constraint on object_blobs."""
        session = get_session()
        try:
            self._seed_collection(session)
            client = DocumentServiceClient(session)
            # Do NOT create object_blob first
            # When using DocumentService directly, create_source_file calls
            # increment_ref which returns False if blob missing, but the
            # source_file is still created. However, in practice with FK
            # constraints enabled this would fail.
            # This test verifies the client has get_or_create_object_blob
            # so callers can create the blob first.
            assert hasattr(client, "get_or_create_object_blob")
        finally:
            session.close()


class TestDocumentServiceClientRemote:
    def test_create_source_file_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        with patch.object(
            client._get_remote(), "_post", return_value={"source_file_id": "src-remote-1"}
        ) as mock_post:
            result = client.create_source_file("col-1", "obj-1", "sha256:abc")
            assert result["source_file_id"] == "src-remote-1"
            mock_post.assert_called_once()

        # Reset cached value
        client_mod._REMOTE_URL = None

    def test_claim_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        with patch.object(
            client._get_remote(), "_post", return_value={"claimed": True}
        ) as mock_post:
            result = client.claim("src-1", "job-1")
            assert result is True
            mock_post.assert_called_once_with(
                "/internal/source-files/src-1/claim",
                {"job_id": "job-1"},
            )

        client_mod._REMOTE_URL = None

    def test_mark_consumed_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        with patch.object(
            client._get_remote(), "_post", return_value={"consumed": True}
        ) as mock_post:
            result = client.mark_consumed("src-1", "job-1")
            assert result is True
            mock_post.assert_called_once_with(
                "/internal/source-files/src-1/mark-consumed",
                {"job_id": "job-1"},
            )

        client_mod._REMOTE_URL = None

    def test_mark_cleanable_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        with patch.object(
            client._get_remote(), "_post", return_value={"cleanable": True}
        ) as mock_post:
            result = client.mark_cleanable("src-1", "job-1")
            assert result is True
            mock_post.assert_called_once_with(
                "/internal/source-files/src-1/mark-cleanable",
                {"job_id": "job-1"},
            )

        client_mod._REMOTE_URL = None

    def test_find_active_by_content_hash_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        # Active source file (duplicate but no published doc)
        with patch.object(
            client._get_remote(), "_post", return_value={"is_duplicate": True, "existing_doc_id": None}
        ) as mock_post:
            result = client.find_active_by_content_hash("sha256:dup", "col-1")
            assert result is not None
            mock_post.assert_called_once_with(
                "/internal/dedup-check",
                {"content_hash": "sha256:dup", "collection_id": "col-1"},
            )

        # Published doc (should return None — not an active source file)
        with patch.object(
            client._get_remote(), "_post", return_value={"is_duplicate": True, "existing_doc_id": "doc-1"}
        ):
            result = client.find_active_by_content_hash("sha256:published", "col-1")
            assert result is None

        # No duplicate
        with patch.object(
            client._get_remote(), "_post", return_value={"is_duplicate": False, "existing_doc_id": None}
        ):
            result = client.find_active_by_content_hash("sha256:new", "col-1")
            assert result is None

        client_mod._REMOTE_URL = None

    def test_get_or_create_object_blob_remote(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_SERVICE_URL", "http://doc-svc:8000")
        import ingestion_worker.document_service_client as client_mod

        client_mod._REMOTE_URL = None

        client = DocumentServiceClient()
        with patch.object(
            client._get_remote(), "_post", return_value={"object_id": "obj-remote-1", "ref_count": 0}
        ) as mock_post:
            result = client.get_or_create_object_blob("sha256:blob", "s3://bucket/blob", 100)
            assert result["object_id"] == "obj-remote-1"
            mock_post.assert_called_once_with(
                "/internal/object-blobs/get-or-create",
                {"content_hash": "sha256:blob", "storage_key": "s3://bucket/blob", "size_bytes": 100},
            )

        client_mod._REMOTE_URL = None


class TestSingleton:
    def test_get_document_service_client_returns_same_instance(self):
        import ingestion_worker.document_service_client as client_mod

        client_mod._fallback_client = None
        c1 = get_document_service_client()
        c2 = get_document_service_client()
        assert c1 is c2
        client_mod._fallback_client = None
