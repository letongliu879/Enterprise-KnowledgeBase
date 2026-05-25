from __future__ import annotations

from pathlib import Path
import os

from indexing_service.contracts import IndexBuildRequestedCommand, IndexRequestType
from indexing_service.jobs.index_job_runner import IndexJobRunner
from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.preview_contracts import ParsePreviewRequestedCommand
from indexing_service.persistent_repository import PersistentIndexingRepository
from reality_rag_persistence.database import create_all, override_url_for_testing
from reality_rag_persistence.repositories import (
    ChunkRegistryRepository,
    IndexBuildJobRepository,
    IndexedDocumentRepository,
    IndexRegistryRepository,
    ParseSnapshotRepository,
)
from reality_rag_persistence.database import get_session


def test_persistent_registry_stores_job_document_and_active_version() -> None:
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    for key in (
        "REALITY_RAG_INDEX_VERSIONS_FILE",
        "REALITY_RAG_INDEXED_CHUNKS_FILE",
        "REALITY_RAG_INDEXED_DOCUMENTS_FILE",
        "REALITY_RAG_PARSE_SNAPSHOTS_FILE",
    ):
        os.environ.pop(key, None)

    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    accepted = preview_runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_persist_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_persist_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_persist_01",
        )
    )

    IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_persist_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_persist_01",
            final_doc_id="doc_persist_01",
            document_version="v1",
            publish_version="pub_01",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=accepted.parse_snapshot_id,
            governance_overlay_ref="",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="",
            approval_decision_ref="",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_col_default_persist",
            idempotency_key="idem_persist_01",
            trace_id="trc_persist_02",
        )
    )

    session = get_session()
    try:
        build_jobs = IndexBuildJobRepository(session)
        chunk_registry = ChunkRegistryRepository(session)
        indexed_documents = IndexedDocumentRepository(session)
        index_registry = IndexRegistryRepository(session)
        parse_snapshots = ParseSnapshotRepository(session)

        persisted_snapshot = parse_snapshots.get(accepted.parse_snapshot_id)
        assert persisted_snapshot is not None
        assert persisted_snapshot.source_file_id == "src_persist_01"
        assert persisted_snapshot.upstream_chunks

        persisted_job = build_jobs.get("ibj_bld_persist_01")
        assert persisted_job is not None
        assert persisted_job.target_index_version == "idxv_col_default_persist"
        assert persisted_job.state.value == "succeeded"

        persisted_document = indexed_documents.get_by_final_doc_and_version(
            "doc_persist_01",
            "idxv_col_default_persist",
        )
        assert persisted_document is not None
        assert persisted_document.parser_id
        assert persisted_document.chunk_count >= 1
        assert persisted_document.state.value == "active"

        persisted_registry = index_registry.get("col_default")
        assert persisted_registry is not None
        assert persisted_registry.index_version == "idxv_col_default_persist"
        assert persisted_registry.status.value == "indexed"

        persisted_chunks = chunk_registry.list_by_index_version("idxv_col_default_persist")
        assert persisted_chunks
        assert any(chunk.final_doc_id == "doc_persist_01" for chunk in persisted_chunks)
    finally:
        session.close()
