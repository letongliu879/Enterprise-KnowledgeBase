"""Tests for chunk revision domain."""

import pytest

from indexing_service.domain import ChunkRecord, IndexVersionRecord
from indexing_service.persistent_repository import PersistentIndexingRepository


def _create_base_chunk(repository):
    chunk = ChunkRecord(
        chunk_id="chunk_base_001",
        tenant_id="tenant_acme",
        collection_id="col_default",
        final_doc_id="doc_001",
        index_version_id="idxv_001",
        document_index_revision_id="dir_001",
        chunk_type="text",
        display_text="Original content",
        vector_text="Original content",
        section_path=["Section 1"],
        page_spans=[{"page_from": 1, "page_to": 1}],
        source_block_ids=["block_1"],
        keyword_terms=["original"],
        confirmed_tags=["tag1"],
        visibility="internal",
        published_document_state="PUBLISHED",
        access_control={"allowed_principal_ids": [], "allowed_groups": []},
        citation_payload={},
        lexical_payload={},
        vector_payload={},
        chunk_hash="sha256:abc",
    )
    repository.chunks_by_index_version.setdefault("idxv_001", []).append(chunk)
    repository.index_versions["idxv_001"] = repository.index_versions.get("idxv_001") or IndexVersionRecord(
        index_version_id="idxv_001",
        tenant_id="tenant_acme",
        collection_id="col_default",
        status="ACTIVE",
        schema_version="2026-05-26",
        index_profile_id="ragflow",
        chunk_profile_id="chunk_default",
        embedding_model="test-model",
        opensearch_index="os_test",
        qdrant_collection="qd_test",
    )
    return chunk


class TestCreateChunkRevision:
    def test_create_revision_success(self):
        repo = PersistentIndexingRepository()
        _create_base_chunk(repo)

        revision = repo.create_chunk_revision(
            revision_id="crv_001",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Updated content",
            vector_text="Updated content",
            idempotency_key="idem_001",
            trace_id="trc_001",
        )
        assert revision.base_evidence_id == "chunk_base_001"
        assert revision.operation == "update"
        assert revision.status == "draft"

    def test_create_revision_not_found(self):
        repo = PersistentIndexingRepository()
        with pytest.raises(KeyError):
            repo.create_chunk_revision(
                revision_id="crv_002",
                base_evidence_id="nonexistent",
                doc_id="doc_001",
                collection_id="col_default",
                tenant_id="tenant_acme",
                operation="update",
                idempotency_key="idem_002",
                trace_id="trc_002",
            )

    def test_create_revision_idempotency(self):
        repo = PersistentIndexingRepository()
        _create_base_chunk(repo)

        revision1 = repo.create_chunk_revision(
            revision_id="crv_003",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Updated content",
            idempotency_key="idem_003",
            trace_id="trc_003",
        )
        revision2 = repo.create_chunk_revision(
            revision_id="crv_004",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Different content",
            idempotency_key="idem_003",
            trace_id="trc_003",
        )
        assert revision1.revision_id == revision2.revision_id

    def test_create_revision_tenant_mismatch(self):
        repo = PersistentIndexingRepository()
        _create_base_chunk(repo)

        with pytest.raises(ValueError):
            repo.create_chunk_revision(
                revision_id="crv_004",
                base_evidence_id="chunk_base_001",
                doc_id="doc_001",
                collection_id="col_default",
                tenant_id="tenant_other",
                operation="update",
                idempotency_key="idem_004",
                trace_id="trc_004",
            )


class TestGetChunkRevision:
    def test_get_revision(self):
        repo = PersistentIndexingRepository()
        _create_base_chunk(repo)
        revision = repo.create_chunk_revision(
            revision_id="crv_001",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Updated",
            idempotency_key="idem_get",
            trace_id="trc_get",
        )

        found = repo.get_chunk_revision(revision.revision_id)
        assert found.revision_id == revision.revision_id

    def test_get_revision_not_found(self):
        repo = PersistentIndexingRepository()
        with pytest.raises(KeyError):
            repo.get_chunk_revision("nonexistent")


class TestMaterializeChunkRevision:
    def test_materialize_success(self):
        repo = PersistentIndexingRepository()
        _create_base_chunk(repo)
        revision = repo.create_chunk_revision(
            revision_id="crv_mat_001",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Materialized content",
            vector_text="Materialized content",
            idempotency_key="idem_mat",
            trace_id="trc_mat",
        )

        result = repo.materialize_chunk_revision(revision.revision_id)
        assert result["status"] == "active"
        assert result["revision_id"] == revision.revision_id

        # Old chunk should be superseded
        old_chunk = next((c for c in repo.list_chunks() if c.chunk_id == "chunk_base_001"), None)
        assert old_chunk is not None
        assert old_chunk.available_int == 0

    def test_materialize_not_found(self):
        repo = PersistentIndexingRepository()
        with pytest.raises(KeyError):
            repo.materialize_chunk_revision("nonexistent")

    def test_materialize_old_chunk_preserved_on_failure(self):
        repo = PersistentIndexingRepository()
        chunk = _create_base_chunk(repo)
        # Remove index version to trigger materialization failure
        del repo.index_versions["idxv_001"]

        revision = repo.create_chunk_revision(
            revision_id="crv_mat_fail",
            base_evidence_id="chunk_base_001",
            doc_id="doc_001",
            collection_id="col_default",
            tenant_id="tenant_acme",
            operation="update",
            content="Should fail",
            idempotency_key="idem_mat_fail",
            trace_id="trc_mat_fail",
        )

        with pytest.raises(RuntimeError):
            repo.materialize_chunk_revision(revision.revision_id)
        # Old chunk should still be available
        assert chunk.available_int == 1
