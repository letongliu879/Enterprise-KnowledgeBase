"""E2E smoke tests for publish-to-retrieval pipeline within indexing service."""

from __future__ import annotations

from pathlib import Path

from indexing_service.contracts import IndexBuildRequestedCommand, IndexRequestType
from indexing_service.domain import IndexVersionStatus
from indexing_service.jobs.index_job_runner import IndexJobRunner
from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.persistent_repository import PersistentIndexingRepository
from reality_rag_contracts import IndexedDocumentState


def test_full_publish_flow_from_preview_to_active_index() -> None:
    """Parse preview -> index build (publish) -> verify activation and queryable chunks."""
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()

    # Step 1: Generate ParseSnapshot via parse preview
    preview_runner = ParsePreviewRunner(repository=repo)
    preview_result = preview_runner.accept(
        __import__("indexing_service.preview_contracts", fromlist=["ParsePreviewRequestedCommand"]).ParsePreviewRequestedCommand(
            request_id="req_e2e_publish_01",
            tenant_id="tnt_e2e",
            collection_id="col_e2e",
            source_file_id="src_e2e_publish_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_e2e_publish_01",
        )
    )
    assert preview_result.parse_snapshot_id

    # Step 2: Submit index build job with request_type=PUBLISH
    job_runner = IndexJobRunner(repo)
    build_result = job_runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_e2e_publish_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_e2e",
            collection_id="col_e2e",
            source_file_id="src_e2e_publish_01",
            final_doc_id="doc_e2e_publish_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=preview_result.parse_snapshot_id,
            governance_overlay_ref="gov://e2e_publish",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://e2e_publish",
            approval_decision_ref="approval://e2e_publish",
            source_metadata={
                "tenant_id": "tnt_e2e",
                "collection_id": "col_e2e",
                "filename": sample.name,
                "allowed_principal_ids": "user_e2e_01",
            },
            index_profile_id="ragflow",
            idempotency_key="idem_e2e_publish_01",
            trace_id="trc_e2e_publish_02",
        )
    )

    # Step 3: Verify job completed successfully
    assert build_result["build_job_id"] == "ibj_bld_e2e_publish_01"
    assert build_result["status"] == "READY"

    # Step 4: Verify index version is ACTIVE
    version = repo.get_index_version("idxv_col_e2e_active")
    assert version.status == IndexVersionStatus.ACTIVE

    # Step 5: Verify indexed document is ACTIVE
    indexed_docs = repo.list_indexed_documents()
    assert len(indexed_docs) == 1
    doc = indexed_docs[0]
    assert doc.final_doc_id == "doc_e2e_publish_01"
    assert doc.state == IndexedDocumentState.ACTIVE
    assert doc.collection_id == "col_e2e"
    assert doc.chunk_count >= 1

    # Step 6: Verify chunks are queryable (retrieval-visible)
    active_chunks = repo.list_active_chunks()
    assert len(active_chunks) >= 1

    # Step 7: Verify access-controlled query returns chunks for allowed principal
    visible = repo.query_chunks(
        tenant_id="tnt_e2e",
        principal_id="user_e2e_01",
        principal_groups=(),
        collection_id="col_e2e",
    )
    assert len(visible) >= 1
    for chunk in visible:
        assert chunk.final_doc_id == "doc_e2e_publish_01"
        assert chunk.collection_id == "col_e2e"
        assert chunk.available_int == 1
        assert chunk.published_document_state == "PUBLISHED"

    # Step 8: Verify asset bundle was written
    bundle = repo.index_asset_bundles[f"idxv_col_e2e_active:doc_e2e_publish_01"]
    assert bundle.opensearch_records
    assert bundle.qdrant_points


def test_reindex_creates_new_active_version_and_replaces_old() -> None:
    """Publish -> reindex -> verify new version active, old version inactive."""
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    preview_result = preview_runner.accept(
        __import__("indexing_service.preview_contracts", fromlist=["ParsePreviewRequestedCommand"]).ParsePreviewRequestedCommand(
            request_id="req_e2e_reindex_01",
            tenant_id="tnt_e2e",
            collection_id="col_e2e_reindex",
            source_file_id="src_e2e_reindex_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_e2e_reindex_01",
        )
    )

    job_runner = IndexJobRunner(repo)

    # First publish
    first = job_runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_e2e_reindex_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_e2e",
            collection_id="col_e2e_reindex",
            source_file_id="src_e2e_reindex_01",
            final_doc_id="doc_e2e_reindex_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=preview_result.parse_snapshot_id,
            governance_overlay_ref="gov://e2e_reindex",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://e2e_reindex",
            approval_decision_ref="approval://e2e_reindex",
            source_metadata={
                "tenant_id": "tnt_e2e",
                "collection_id": "col_e2e_reindex",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_e2e_reindex_v1",
            idempotency_key="idem_e2e_reindex_01",
            trace_id="trc_e2e_reindex_02",
        )
    )
    assert first["status"] == "READY"
    assert repo.get_index_version("idxv_e2e_reindex_v1").status == IndexVersionStatus.ACTIVE

    # Reindex with new version
    second = job_runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_e2e_reindex_02",
            request_type=IndexRequestType.REINDEX,
            tenant_id="tnt_e2e",
            collection_id="col_e2e_reindex",
            source_file_id="src_e2e_reindex_01",
            final_doc_id="doc_e2e_reindex_01",
            document_version="v2",
            publish_version="p2",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=preview_result.parse_snapshot_id,
            governance_overlay_ref="gov://e2e_reindex",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://e2e_reindex",
            approval_decision_ref="approval://e2e_reindex",
            source_metadata={
                "tenant_id": "tnt_e2e",
                "collection_id": "col_e2e_reindex",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_e2e_reindex_v2",
            idempotency_key="idem_e2e_reindex_02",
            trace_id="trc_e2e_reindex_03",
        )
    )
    assert second["status"] == "READY"

    # Verify version states
    v1 = repo.get_index_version("idxv_e2e_reindex_v1")
    v2 = repo.get_index_version("idxv_e2e_reindex_v2")
    assert v1.status == IndexVersionStatus.INACTIVE
    assert v1.replaced_by_index_version_id == "idxv_e2e_reindex_v2"
    assert v2.status == IndexVersionStatus.ACTIVE
    assert v2.previous_active_index_version_id == "idxv_e2e_reindex_v1"

    # Verify indexed document states
    docs_by_version = {doc.index_version: doc.state for doc in repo.list_indexed_documents()}
    assert docs_by_version["idxv_e2e_reindex_v1"] == IndexedDocumentState.CANDIDATE
    assert docs_by_version["idxv_e2e_reindex_v2"] == IndexedDocumentState.ACTIVE

    # Verify active chunks belong to new version only
    active_chunks = repo.list_active_chunks()
    assert all(chunk.index_version_id == "idxv_e2e_reindex_v2" for chunk in active_chunks)

    # Verify query returns new version chunks
    visible = repo.query_chunks(
        tenant_id="tnt_e2e",
        principal_id="user_e2e_01",
        principal_groups=(),
        collection_id="col_e2e_reindex",
    )
    assert len(visible) >= 1
    assert all(chunk.index_version_id == "idxv_e2e_reindex_v2" for chunk in visible)


def test_rejected_document_state_propagates_to_chunks() -> None:
    """Build with rejected approval decision -> chunks marked REJECTED but still materialized."""
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    preview_result = preview_runner.accept(
        __import__("indexing_service.preview_contracts", fromlist=["ParsePreviewRequestedCommand"]).ParsePreviewRequestedCommand(
            request_id="req_e2e_reject_01",
            tenant_id="tnt_e2e",
            collection_id="col_e2e_reject",
            source_file_id="src_e2e_reject_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_e2e_reject_01",
        )
    )

    import json
    from pathlib import Path as _Path
    approval_ref = _Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-approval-rejected.json")
    approval_ref.write_text(
        json.dumps({
            "decision": "reject",
            "actor_id": "reviewer_01",
            "ticket_id": "apt_reject_01",
            "auto_approved": False,
        }),
        encoding="utf-8",
    )

    job_runner = IndexJobRunner(repo)
    build_result = job_runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_e2e_reject_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_e2e",
            collection_id="col_e2e_reject",
            source_file_id="src_e2e_reject_01",
            final_doc_id="doc_e2e_reject_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=preview_result.parse_snapshot_id,
            governance_overlay_ref="gov://e2e_reject",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://e2e_reject",
            approval_decision_ref=str(approval_ref),
            source_metadata={
                "tenant_id": "tnt_e2e",
                "collection_id": "col_e2e_reject",
                "filename": sample.name,
                "allowed_principal_ids": "user_e2e_01",
            },
            index_profile_id="ragflow",
            idempotency_key="idem_e2e_reject_01",
            trace_id="trc_e2e_reject_02",
        )
    )
    assert build_result["status"] == "READY"

    # Verify chunks are built with REJECTED state
    active_chunks = repo.list_active_chunks()
    assert len(active_chunks) >= 1
    for chunk in active_chunks:
        assert chunk.published_document_state == "REJECTED"

    # Verify chunks are queryable at indexing layer (retrieval filters by state)
    visible = repo.query_chunks(
        tenant_id="tnt_e2e",
        principal_id="user_e2e_01",
        principal_groups=(),
        collection_id="col_e2e_reject",
    )
    assert len(visible) >= 1
    for chunk in visible:
        assert chunk.published_document_state == "REJECTED"


def test_query_chunks_filters_by_access_control() -> None:
    """Published chunks are only visible to allowed principals."""
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = PersistentIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    preview_result = preview_runner.accept(
        __import__("indexing_service.preview_contracts", fromlist=["ParsePreviewRequestedCommand"]).ParsePreviewRequestedCommand(
            request_id="req_e2e_acl_01",
            tenant_id="tnt_e2e",
            collection_id="col_e2e_acl",
            source_file_id="src_e2e_acl_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_e2e_acl_01",
        )
    )

    job_runner = IndexJobRunner(repo)
    job_runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_e2e_acl_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_e2e",
            collection_id="col_e2e_acl",
            source_file_id="src_e2e_acl_01",
            final_doc_id="doc_e2e_acl_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=preview_result.parse_snapshot_id,
            governance_overlay_ref="gov://e2e_acl",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://e2e_acl",
            approval_decision_ref="approval://e2e_acl",
            source_metadata={
                "tenant_id": "tnt_e2e",
                "collection_id": "col_e2e_acl",
                "filename": sample.name,
                "allowed_principal_ids": "allowed_user",
            },
            index_profile_id="ragflow",
            idempotency_key="idem_e2e_acl_01",
            trace_id="trc_e2e_acl_02",
        )
    )

    # Allowed principal sees chunks
    allowed = repo.query_chunks(
        tenant_id="tnt_e2e",
        principal_id="allowed_user",
        principal_groups=(),
        collection_id="col_e2e_acl",
    )
    assert len(allowed) >= 1

    # Different principal is denied
    denied = repo.query_chunks(
        tenant_id="tnt_e2e",
        principal_id="other_user",
        principal_groups=(),
        collection_id="col_e2e_acl",
    )
    assert len(denied) == 0

    # Different tenant is denied
    denied_tenant = repo.query_chunks(
        tenant_id="tnt_other",
        principal_id="allowed_user",
        principal_groups=(),
        collection_id="col_e2e_acl",
    )
    assert len(denied_tenant) == 0
