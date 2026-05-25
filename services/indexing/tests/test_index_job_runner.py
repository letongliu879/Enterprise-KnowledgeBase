from __future__ import annotations

import json
from pathlib import Path

from indexing_service.contracts import IndexBuildRequestedCommand, IndexRequestType
from indexing_service.domain import IndexVersionStatus
from indexing_service.jobs.index_job_runner import IndexJobRunner
from indexing_service.jobs.parse_preview_runner import ParsePreviewRunner
from indexing_service.preview_contracts import ParsePreviewRequestedCommand
from indexing_service.repository import InMemoryIndexingRepository
from indexing_service.versioning.cleanup import CleanupService
from indexing_service.versioning.rollback import RollbackService
from indexing_service.domain import ParseSnapshotRecord
from reality_rag_contracts import IndexedDocumentState


def test_index_job_builds_index_asset_bundle() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = InMemoryIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    accepted = preview_runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_index_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_index_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_test_index_01",
        )
    )

    runner = IndexJobRunner(repo)
    result = runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_test_index_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_index_01",
            final_doc_id="doc_test_index_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=accepted.parse_snapshot_id,
            governance_overlay_ref="gov://test",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://test",
            approval_decision_ref="approval://test",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            idempotency_key="idem_test_index_01",
            trace_id="trc_test_index_02",
        )
    )

    assert result["build_job_id"] == "ibj_bld_test_index_01"
    assert result["status"] == "READY"
    assert repo.list_chunks()
    assert repo.index_asset_bundles
    bundle = next(iter(repo.index_asset_bundles.values()))
    assert bundle.indexed_document_id
    assert bundle.opensearch_records
    assert bundle.qdrant_points
    assert isinstance(bundle.document_metadata, dict)
    assert bundle.opensearch_records[0].body["indexed_document_id"] == bundle.indexed_document_id
    assert bundle.opensearch_records[0].body["id"] == bundle.opensearch_records[0].document_id
    assert bundle.opensearch_records[0].body["kb_id"] == "col_default"
    assert bundle.opensearch_records[0].body["doc_id"] == "doc_test_index_01"
    assert bundle.opensearch_records[0].body["create_time"]
    assert bundle.opensearch_records[0].body["create_timestamp_flt"] > 0
    assert bundle.opensearch_records[0].body["content_with_weight"]
    assert bundle.opensearch_records[0].body["content_ltks"]
    assert bundle.opensearch_records[0].body["content_sm_ltks"]
    assert bundle.opensearch_records[0].body["removed_kwd"] == "N"
    assert bundle.opensearch_records[0].body["source_id"] == ["src_test_index_01"]
    assert "doc_type_kwd" in bundle.opensearch_records[0].body
    assert "position_int" in bundle.opensearch_records[0].body
    assert "page_num_int" in bundle.opensearch_records[0].body
    assert "top_int" in bundle.opensearch_records[0].body
    assert bundle.qdrant_points[0].payload["indexed_document_id"] == bundle.indexed_document_id
    assert bundle.qdrant_points[0].payload["id"] == bundle.qdrant_points[0].point_id
    assert bundle.qdrant_points[0].payload["kb_id"] == "col_default"
    assert bundle.qdrant_points[0].payload["doc_id"] == "doc_test_index_01"
    version = repo.get_index_version("idxv_col_default_active")
    assert version.status == IndexVersionStatus.ACTIVE
    assert repo.list_active_chunks()
    indexed_documents = repo.list_indexed_documents()
    assert len(indexed_documents) == 1
    assert indexed_documents[0].state == IndexedDocumentState.ACTIVE
    assert indexed_documents[0].parser_id
    assert indexed_documents[0].source_suffix
    assert indexed_documents[0].chunk_count >= 1
    assert indexed_documents[0].visible_chunk_count >= 1
    assert indexed_documents[0].hidden_chunk_count >= 0


def test_publish_activation_rollback_and_cleanup() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    repo = InMemoryIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    accepted = preview_runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_test_index_lifecycle_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_index_lifecycle_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_test_index_lifecycle_01",
        )
    )

    runner = IndexJobRunner(repo)
    first = runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_test_index_lifecycle_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_index_lifecycle_01",
            final_doc_id="doc_test_index_lifecycle_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=accepted.parse_snapshot_id,
            governance_overlay_ref="gov://test",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://test",
            approval_decision_ref="approval://test",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_col_default_v1",
            idempotency_key="idem_test_index_lifecycle_01",
            trace_id="trc_test_index_lifecycle_02",
        )
    )
    assert first["status"] == "READY"
    assert repo.get_index_version("idxv_col_default_v1").status == IndexVersionStatus.ACTIVE

    second = runner.accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_test_index_lifecycle_02",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_test_index_lifecycle_01",
            final_doc_id="doc_test_index_lifecycle_01",
            document_version="v2",
            publish_version="p2",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=accepted.parse_snapshot_id,
            governance_overlay_ref="gov://test",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://test",
            approval_decision_ref="approval://test",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": sample.name,
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_col_default_v2",
            idempotency_key="idem_test_index_lifecycle_02",
            trace_id="trc_test_index_lifecycle_03",
        )
    )
    assert second["status"] == "READY"
    first_version = repo.get_index_version("idxv_col_default_v1")
    second_version = repo.get_index_version("idxv_col_default_v2")
    assert first_version.status == IndexVersionStatus.INACTIVE
    assert first_version.replaced_by_index_version_id == "idxv_col_default_v2"
    assert second_version.status == IndexVersionStatus.ACTIVE
    assert second_version.previous_active_index_version_id == "idxv_col_default_v1"
    active_docs = {doc.index_version: doc.state for doc in repo.list_indexed_documents()}
    assert active_docs["idxv_col_default_v1"] == IndexedDocumentState.CANDIDATE
    assert active_docs["idxv_col_default_v2"] == IndexedDocumentState.ACTIVE

    rollback_receipt = RollbackService(repo).rollback("idxv_col_default_v2")
    assert rollback_receipt.reactivated_index_version_id == "idxv_col_default_v1"
    assert repo.get_index_version("idxv_col_default_v2").status == IndexVersionStatus.ROLLED_BACK
    assert repo.get_index_version("idxv_col_default_v1").status == IndexVersionStatus.ACTIVE
    rollback_states = {doc.index_version: doc.state for doc in repo.list_indexed_documents()}
    assert rollback_states["idxv_col_default_v2"] == IndexedDocumentState.CANDIDATE
    assert rollback_states["idxv_col_default_v1"] == IndexedDocumentState.ACTIVE

    cleanup_receipt = CleanupService(repo).cleanup("idxv_col_default_v2")
    assert cleanup_receipt.removed_chunk_count > 0
    assert repo.get_index_version("idxv_col_default_v2").status == IndexVersionStatus.DISCARDED
    assert not any(chunk.index_version_id == "idxv_col_default_v2" for chunk in repo.list_chunks())
    assert all(chunk.index_version_id == "idxv_col_default_v1" for chunk in repo.list_active_chunks())
    assert all(doc.index_version != "idxv_col_default_v2" for doc in repo.list_indexed_documents())


def test_presentation_chunks_preserve_slide_semantics() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_presentation_01",
            request_id="req_presentation_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_presentation_01",
            source_binary_ref="asset://presentation",
            source_filename="Quarterly Business Review.pptx",
            source_suffix="pptx",
            parser_id="presentation",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={},
            input_hash="sha256:presentation",
            preview_text="Revenue Growth\nQ1 revenue grew 23%.",
            upstream_chunks=[
                {
                    "docnm_kwd": "Quarterly Business Review.pptx",
                    "title_tks": "quarterly business review",
                    "content_with_weight": "Revenue Growth\nQ1 revenue grew 23%.",
                    "content_ltks": "revenue growth q1 revenue grew 23",
                    "content_sm_ltks": "revenue growth q1 revenue grew 23",
                    "doc_type_kwd": "image",
                    "page_num_int": [3],
                    "top_int": [0],
                    "position_int": [(3, 0, 0, 0, 0)],
                }
            ],
            outline=["Quarterly Business Review"],
            document_metadata={"title": "Quarterly Business Review"},
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:presentation",
        )
    )

    result = IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_presentation_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_presentation_01",
            final_doc_id="doc_presentation_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://presentation",
            parse_snapshot_id="pss_presentation_01",
            governance_overlay_ref="gov://presentation",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://presentation",
            approval_decision_ref="approval://presentation",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "Quarterly Business Review.pptx",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_presentation_01",
            idempotency_key="idem_presentation_01",
            trace_id="trc_presentation_01",
        )
    )

    assert result["status"] == "READY"
    chunks = repo.list_active_chunks()
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == "mixed"
    assert chunk.section_path == ["Quarterly Business Review", "Slide 3"]
    assert chunk.citation_payload["anchor"] == "slide:3-3:chunk:1"
    assert chunk.citation_payload["slide_number"] == 3
    assert chunk.citation_payload["page_kind"] == "slide"
    assert chunk.metadata["slide_number"] == 3
    assert chunk.metadata["parser_id"] == "presentation"


def test_paper_chunks_preserve_authors_and_keywords() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_paper_01",
            request_id="req_paper_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_paper_01",
            source_binary_ref="asset://paper",
            source_filename="rag-paper.pdf",
            source_suffix="pdf",
            parser_id="paper",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={},
            input_hash="sha256:paper",
            preview_text="Abstract\nThis paper studies retrieval augmentation.",
            upstream_chunks=[
                {
                    "docnm_kwd": "rag-paper.pdf",
                    "title_tks": "rag paper",
                    "authors_tks": "Alice Bob",
                    "authors_sm_tks": "Alice Bob",
                    "important_kwd": ["abstract", "summary"],
                    "important_tks": "abstract summary",
                    "content_with_weight": "This paper studies retrieval augmentation.",
                    "content_ltks": "This paper studies retrieval augmentation",
                    "content_sm_ltks": "This paper studies retrieval augmentation",
                    "page_num_int": [1],
                    "top_int": [10],
                    "position_int": [(1, 0, 100, 10, 40)],
                }
            ],
            outline=["RAG Paper"],
            document_metadata={"title": "RAG Paper"},
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:paper",
        )
    )

    result = IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_paper_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_paper_01",
            final_doc_id="doc_paper_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://paper",
            parse_snapshot_id="pss_paper_01",
            governance_overlay_ref="gov://paper",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://paper",
            approval_decision_ref="approval://paper",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "rag-paper.pdf",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_paper_01",
            idempotency_key="idem_paper_01",
            trace_id="trc_paper_01",
        )
    )

    assert result["status"] == "READY"
    chunk = repo.list_active_chunks()[0]
    assert chunk.metadata["parser_id"] == "paper"
    assert chunk.metadata["authors"] == "Alice Bob"
    assert chunk.metadata["important_kwd"] == ["abstract", "summary"]
    assert chunk.authors_tks == "Alice Bob"
    assert chunk.authors_sm_tks == "Alice Bob"
    assert chunk.important_kwd == ["abstract", "summary"]
    assert chunk.title_text == "rag-paper.pdf"
    assert chunk.embedding_text == "This paper studies retrieval augmentation."
    assert chunk.vector_text == "This paper studies retrieval augmentation."
    assert chunk.embedding_title_weight == 0.1
    assert chunk.vector_payload["title_text"] == "rag-paper.pdf"
    assert chunk.vector_payload["embedding_text"] == "This paper studies retrieval augmentation."
    assert chunk.vector_payload["embedding_title_weight"] == 0.1
    assert "abstract" in chunk.keyword_terms


def test_manual_chunks_prefer_section_paths_from_upstream() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_manual_01",
            request_id="req_manual_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_manual_01",
            source_binary_ref="asset://manual",
            source_filename="manual.pdf",
            source_suffix="pdf",
            parser_id="manual",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={},
            input_hash="sha256:manual",
            preview_text="Install Guide\nStep 1: Prepare environment.",
            upstream_chunks=[
                {
                    "docnm_kwd": "manual.pdf",
                    "title_tks": "install guide",
                    "content_with_weight": "Step 1: Prepare environment.",
                    "content_ltks": "Step 1 Prepare environment",
                    "content_sm_ltks": "Step 1 Prepare environment",
                    "section_paths": ["Install Guide", "Environment Setup"],
                    "__outline__": [{"title": "Install Guide", "depth": 0}],
                    "page_num_int": [2],
                    "top_int": [20],
                    "position_int": [(2, 0, 100, 20, 50)],
                }
            ],
            outline=["Install Guide"],
            document_metadata={"title": "Install Guide"},
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:manual",
        )
    )

    result = IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_manual_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_manual_01",
            final_doc_id="doc_manual_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://manual",
            parse_snapshot_id="pss_manual_01",
            governance_overlay_ref="gov://manual",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://manual",
            approval_decision_ref="approval://manual",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "manual.pdf",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_manual_01",
            idempotency_key="idem_manual_01",
            trace_id="trc_manual_01",
        )
    )

    assert result["status"] == "READY"
    chunk = repo.list_active_chunks()[0]
    assert chunk.section_path == ["Install Guide", "Environment Setup"]
    assert chunk.metadata["parser_id"] == "manual"


def test_qa_chunks_preserve_question_semantics() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_qa_01",
            request_id="req_qa_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_qa_01",
            source_binary_ref="asset://qa",
            source_filename="faq.txt",
            source_suffix="txt",
            parser_id="qa",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={},
            input_hash="sha256:qa",
            preview_text="Q: How to reimburse?\nA: Submit receipts within 30 days.",
            upstream_chunks=[
                {
                    "docnm_kwd": "faq.txt",
                    "title_tks": "faq",
                    "question_kwd": ["How to reimburse?"],
                    "question_tks": "How to reimburse",
                    "content_with_weight": "Question: How to reimburse?\tAnswer: Submit receipts within 30 days.",
                    "content_ltks": "How to reimburse",
                    "content_sm_ltks": "How to reimburse",
                    "page_num_int": [1],
                    "top_int": [5],
                    "position_int": [(1, 0, 100, 5, 35)],
                }
            ],
            outline=["FAQ"],
            document_metadata={"title": "FAQ"},
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:qa",
        )
    )

    result = IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_qa_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_qa_01",
            final_doc_id="doc_qa_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://qa",
            parse_snapshot_id="pss_qa_01",
            governance_overlay_ref="gov://qa",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://qa",
            approval_decision_ref="approval://qa",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "faq.txt",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_qa_01",
            idempotency_key="idem_qa_01",
            trace_id="trc_qa_01",
        )
    )

    assert result["status"] == "READY"
    chunk = repo.list_active_chunks()[0]
    assert chunk.section_path == ["FAQ", "How to reimburse?"]
    assert chunk.metadata["parser_id"] == "qa"
    assert chunk.metadata["qa_question"] == "How to reimburse?"
    assert chunk.title_text == "faq.txt"
    assert chunk.embedding_text == "How to reimburse?"
    assert chunk.question_kwd == ["How to reimburse?"]
    assert chunk.vector_text == "How to reimburse?"


def test_hidden_parent_and_toc_chunks_are_materialized_but_not_query_visible() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_hidden_01",
            request_id="req_hidden_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_hidden_01",
            source_binary_ref="asset://hidden",
            source_filename="policy.pdf",
            source_suffix="pdf",
            parser_id="naive",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={"toc_extraction": True},
            input_hash="sha256:hidden",
            preview_text="Policy\nSection A",
            upstream_chunks=[
                {
                    "docnm_kwd": "policy.pdf",
                    "title_tks": "policy",
                    "content_with_weight": "Section A content.",
                    "content_ltks": "Section A content",
                    "content_sm_ltks": "Section A content",
                    "mom": "Parent summary text",
                    "page_num_int": [1],
                    "top_int": [1],
                    "position_int": [(1, 0, 100, 1, 20)],
                }
            ],
            outline=["Policy"],
            document_metadata={
                "title": "Policy",
                "outline": [{"level": "0", "title": "Section A", "chunk_id": 0}],
            },
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:naive",
        )
    )

    IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_hidden_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_hidden_01",
            final_doc_id="doc_hidden_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://hidden",
            parse_snapshot_id="pss_hidden_01",
            governance_overlay_ref="gov://hidden",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://hidden",
            approval_decision_ref="approval://hidden",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "policy.pdf",
                "allowed_principal_ids": "user_01",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_hidden_01",
            idempotency_key="idem_hidden_01",
            trace_id="trc_hidden_01",
        )
    )

    all_active = repo.list_active_chunks()
    assert len(all_active) == 3
    assert len([chunk for chunk in all_active if chunk.available_int == 1]) == 1
    assert len([chunk for chunk in all_active if chunk.metadata.get("is_parent_chunk")]) == 1
    assert len([chunk for chunk in all_active if chunk.metadata.get("is_toc_chunk")]) == 1
    toc_chunk = next(chunk for chunk in all_active if chunk.metadata.get("is_toc_chunk"))
    assert "\"ids\"" in toc_chunk.display_text

    visible = repo.query_chunks(
        tenant_id="tnt_default",
        principal_id="user_01",
        principal_groups=(),
        collection_id="col_default",
    )
    assert len(visible) == 1
    assert visible[0].display_text == "Section A content."


def test_table_document_metadata_is_promoted_to_bundle() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_table_01",
            request_id="req_table_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_table_01",
            source_binary_ref="asset://table",
            source_filename="employees.xlsx",
            source_suffix="xlsx",
            parser_id="table",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={
                "table_column_mode": "manual",
                "table_column_roles": {"name": "metadata", "dept": "both"},
                "table_column_names": ["name", "dept"],
            },
            input_hash="sha256:table",
            preview_text="name dept",
            upstream_chunks=[
                {
                    "docnm_kwd": "employees.xlsx",
                    "title_tks": "employees",
                    "content_with_weight": "Alice HR",
                    "content_ltks": "Alice HR",
                    "content_sm_ltks": "Alice HR",
                    "name_raw": "Alice",
                    "name_tks": "Alice",
                    "dept_raw": "HR",
                    "dept_tks": "HR",
                    "page_num_int": [1],
                    "top_int": [1],
                    "position_int": [(1, 0, 100, 1, 20)],
                }
            ],
            outline=["Employees"],
            document_metadata={"name": ["Alice"], "dept": ["HR"]},
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:table",
        )
    )

    IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_table_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_table_01",
            final_doc_id="doc_table_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://table",
            parse_snapshot_id="pss_table_01",
            governance_overlay_ref="gov://table",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://table",
            approval_decision_ref="approval://table",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "employees.xlsx",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_table_01",
            idempotency_key="idem_table_01",
            trace_id="trc_table_01",
        )
    )

    bundle = repo.index_asset_bundles["idxv_table_01:doc_table_01"]
    assert bundle.document_metadata["name"] == ["Alice"]
    assert bundle.document_metadata["dept"] == ["HR"]
    indexed_document = next(doc for doc in repo.list_indexed_documents() if doc.index_version == "idxv_table_01")
    assert indexed_document.parser_id == "table"
    assert indexed_document.source_suffix == "xlsx"
    assert indexed_document.document_metadata["name"] == ["Alice"]
    assert indexed_document.document_metadata["dept"] == ["HR"]
    assert indexed_document.outline
    assert "ids" in indexed_document.outline[0]
    assert bundle.indexed_document_id == indexed_document.indexed_document_id


def test_indexed_document_flags_hidden_record_kinds() -> None:
    repo = InMemoryIndexingRepository()
    repo.save_parse_snapshot(
        ParseSnapshotRecord(
            parse_snapshot_id="pss_flags_01",
            request_id="req_flags_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_flags_01",
            source_binary_ref="asset://flags",
            source_filename="policy.pdf",
            source_suffix="pdf",
            parser_id="naive",
            parser_backend="ragflow_app",
            collection_parser_config={},
            parser_config={"toc_extraction": True},
            input_hash="sha256:flags",
            preview_text="Policy\nSection A",
            upstream_chunks=[
                {
                    "docnm_kwd": "policy.pdf",
                    "title_tks": "policy",
                    "content_with_weight": "Section A content.",
                    "content_ltks": "Section A content",
                    "content_sm_ltks": "Section A content",
                    "mom": "Parent summary text",
                    "page_num_int": [1],
                    "top_int": [1],
                    "position_int": [(1, 0, 100, 1, 20)],
                }
            ],
            outline=["Policy"],
            document_metadata={
                "title": "Policy",
                "outline": [{"level": "0", "title": "Section A", "chunk_id": 0}],
            },
            chunk_preview=[],
            warnings=[],
            decision_reason="upstream:file_service.get_parser:naive",
        )
    )

    IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_flags_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_flags_01",
            final_doc_id="doc_flags_01",
            document_version="v1",
            publish_version="p1",
            visibility="internal",
            source_binary_ref="asset://flags",
            parse_snapshot_id="pss_flags_01",
            governance_overlay_ref="gov://flags",
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref="meta://flags",
            approval_decision_ref="approval://flags",
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": "policy.pdf",
            },
            index_profile_id="ragflow",
            target_index_version_id="idxv_flags_01",
            idempotency_key="idem_flags_01",
            trace_id="trc_flags_01",
        )
    )

    indexed_document = next(doc for doc in repo.list_indexed_documents() if doc.index_version == "idxv_flags_01")
    assert indexed_document.has_parent_chunk is True
    assert indexed_document.has_toc_chunk is True


def test_governance_assets_are_projected_into_formal_indexing() -> None:
    sample = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-preview-qa.txt")
    assert sample.exists()

    overlay_ref = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-governance-overlay.json")
    approval_ref = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-approval.json")
    metadata_ref = Path(r"C:\Users\LLT\AppData\Local\Temp\ekb-metadata.json")
    overlay_ref.write_text(
        json.dumps(
            {
                "source_file_id": "src_gov_01",
                "final_doc_id": "doc_governed_final",
                "visibility": "restricted",
                "confirmed_tags": ["finance", "policy"],
                "publish_version": "pub_governed_02",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    approval_ref.write_text(
        json.dumps(
            {
                "decision": "approve",
                "actor_id": "approver_01",
                "confirmed_tags": ["finance", "approval"],
                "ticket_id": "apt_01",
                "auto_approved": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    metadata_ref.write_text(
        json.dumps(
            {
                "authority_level": 4,
                "department": "finance",
                "retention_policy": "enterprise",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    repo = InMemoryIndexingRepository()
    preview_runner = ParsePreviewRunner(repository=repo)
    accepted = preview_runner.accept(
        ParsePreviewRequestedCommand(
            request_id="req_gov_01",
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_gov_01",
            source_binary_ref=str(sample),
            filename=sample.name,
            mime_type="text/plain",
            trace_id="trc_gov_01",
        )
    )

    IndexJobRunner(repo).accept(
        IndexBuildRequestedCommand(
            build_request_id="bld_gov_01",
            request_type=IndexRequestType.PUBLISH,
            tenant_id="tnt_default",
            collection_id="col_default",
            source_file_id="src_gov_01",
            final_doc_id="doc_should_be_overridden",
            document_version="v1",
            publish_version="pub_should_be_overridden",
            visibility="internal",
            source_binary_ref=str(sample),
            parse_snapshot_id=accepted.parse_snapshot_id,
            governance_overlay_ref=str(overlay_ref),
            sanitized_asset_ref="asset://sanitized",
            canonical_asset_ref="asset://canonical",
            metadata_ref=str(metadata_ref),
            approval_decision_ref=str(approval_ref),
            source_metadata={
                "tenant_id": "tnt_default",
                "collection_id": "col_default",
                "filename": sample.name,
                "allowed_principal_ids": "user_finance",
                "allowed_groups": "group_finance",
            },
            confirmed_tags=["ignored_tag"],
            index_profile_id="ragflow",
            idempotency_key="idem_gov_01",
            trace_id="trc_gov_02",
        )
    )

    active_chunk = repo.list_active_chunks()[0]
    assert active_chunk.final_doc_id == "doc_governed_final"
    assert active_chunk.visibility == "restricted"
    assert active_chunk.confirmed_tags == ["finance", "approval"]
    assert active_chunk.published_document_state == "PUBLISHED"
    assert active_chunk.metadata["governance"]["publish_version"] == "pub_governed_02"
    assert active_chunk.metadata["doc_metadata"]["governance_metadata"]["department"] == "finance"
    assert active_chunk.metadata["approval"]["actor_id"] == "approver_01"
    assert active_chunk.lexical_payload["governance"]["final_doc_id"] == "doc_governed_final"
    assert active_chunk.vector_payload["governance"]["visibility"] == "restricted"

    bundle = repo.index_asset_bundles["idxv_col_default_active:doc_governed_final"]
    assert bundle.document_metadata["governance_overlay"]["final_doc_id"] == "doc_governed_final"
    assert bundle.document_metadata["approval"]["actor_id"] == "approver_01"
    assert bundle.document_metadata["governance_metadata"]["retention_policy"] == "enterprise"
    assert bundle.opensearch_records[0].body["governance"]["visibility"] == "restricted"
    assert bundle.qdrant_points[0].payload["governance"]["confirmed_tags"] == ["finance", "approval"]

    indexed_document = repo.list_indexed_documents()[0]
    assert indexed_document.final_doc_id == "doc_governed_final"
    assert indexed_document.document_metadata["governance_overlay"]["publish_version"] == "pub_governed_02"
    assert indexed_document.document_metadata["approval"]["ticket_id"] == "apt_01"
