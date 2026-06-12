"""Tests for document projection behavior."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from reality_rag_persistence.models import (
    ChunkRegistryModel,
    DocumentModel,
    IndexedDocumentModel,
    IntakeJobModel,
    ParseSnapshotModel,
    PublishedDocumentModel,
    SourceFileModel,
)

from workbench_api.projections.projector import ProjectionProjector
from workbench_api.projections.reconciler import ProjectionReconciler
from workbench_api.projections.repository import DocumentProjectionRepository


def _make_document_event(
    event_id: str,
    event_type: str,
    doc_id: str,
    version: int,
    payload: dict,
) -> dict:
    from datetime import datetime, timezone

    return {
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "document",
        "aggregate_id": doc_id,
        "aggregate_version": version,
        "occurred_at": datetime.now(timezone.utc),
        "payload": {
            "doc_id": doc_id,
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            **payload,
        },
        "trace_id": f"trace-{doc_id}",
    }


def test_document_projection_preserves_snapshot_fields_across_partial_updates(
    db_session: Session,
):
    projector = ProjectionProjector(db_session)
    doc_id = "doc_001"

    assert projector.record_and_apply(
        _make_document_event(
            "ev_parse",
            "ParseSnapshotCompleted",
            doc_id,
            10,
            {
                "source_file_id": "sf_001",
                "parse_snapshot_id": "ps_001",
                "page_count": 7,
                "parser_profile_id": "parser_001",
                "parser_profile_name": "Default Parser",
                "document_state": "PARSED",
            },
        )
    )["applied"]

    assert projector.record_and_apply(
        _make_document_event(
            "ev_chunks",
            "ChunksMaterialized",
            doc_id,
            20,
            {
                "chunk_count": 22,
            },
        )
    )["applied"]

    assert projector.record_and_apply(
        _make_document_event(
            "ev_publish",
            "PublishCompleted",
            doc_id,
            40,
            {
                "publish_state": "published",
                "active_index_version": "idx_v1",
            },
        )
    )["applied"]
    db_session.commit()

    projection = DocumentProjectionRepository(db_session).get(doc_id)
    assert projection is not None
    assert projection.parse_snapshot_id == "ps_001"
    assert projection.source_file_id == "sf_001"
    assert projection.page_count == 7
    assert projection.chunk_count == 22
    assert projection.active_index_version == "idx_v1"


class _UnusedClient:
    pass


import tempfile
from pathlib import Path


def test_document_reconcile_backfills_from_local_tables(db_session: Session):
    doc_id = "doc_001"
    source_file_id = "sf_001"
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = Path(tmp_dir) / "doc-source.txt"
        source_path.write_text("hello", encoding="utf-8")

        db_session.add(
            PublishedDocumentModel(
                published_document_id="pub_001",
                final_doc_id=doc_id,
                logical_document_id=doc_id,
                tenant_id="tenant_acme",
                collection_id="col_default",
                state="PUBLISHED",
                active_index_version="v1",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db_session.add(
            DocumentModel(
                doc_id=doc_id,
                logical_document_id=doc_id,
                tenant_id="tenant_acme",
                collection_id="col_default",
                source_hash="sha256:x",
                source_content_hash="sha256:x",
                publish_status="published",
                index_status="indexed",
            )
        )
        db_session.add(
            SourceFileModel(
                source_file_id=source_file_id,
                upload_id="upload_001",
                object_id="obj_001",
                collection_id="col_default",
                visibility="INTERNAL",
                original_name="example.txt",
                sanitized_name="example.txt",
                content_hash="sha256:x",
                size_bytes=5,
                state="cleanable",
                claimed_by_job_id="job_001",
            )
        )
        db_session.add(
            IntakeJobModel(
                intake_job_id="job_001",
                source_file_id=source_file_id,
                object_id="obj_001",
                collection_id="col_default",
                state="published",
                state_version=10,
                current_stage="publishing",
                preliminary_doc_id=doc_id,
                final_doc_id=doc_id,
                ticket_id="ticket_001",
                trace_id="upload_001",
            )
        )
        db_session.add(
            ParseSnapshotModel(
                parse_snapshot_id="ps_001",
                request_id="req_001",
                tenant_id="tenant_acme",
                collection_id="col_default",
                source_file_id=source_file_id,
                source_binary_ref=str(source_path),
                source_filename="example.txt",
                source_suffix="txt",
                parser_id="naive",
                parser_backend="ragflow_app",
                input_hash="sha256:x",
                preview_text="hello",
            )
        )
        db_session.add(
            IndexedDocumentModel(
                indexed_document_id="idx_001",
                final_doc_id=doc_id,
                collection_id="col_default",
                index_version="v1",
                parser_id="naive",
                source_suffix="txt",
                chunk_count=2,
                embedding_count=2,
                visible_chunk_count=2,
                hidden_chunk_count=0,
                state="active",
            )
        )
        db_session.add(
            ChunkRegistryModel(
                chunk_id="chk_001",
                tenant_id="tenant_acme",
                collection_id="col_default",
                final_doc_id=doc_id,
                index_version_id="v1",
                available_int=1,
                visibility="INTERNAL",
                payload_json={
                    "chunk_id": "chk_001",
                    "final_doc_id": doc_id,
                    "display_text": "hello",
                    "page_spans": [{"page_from": 1, "page_to": 3}],
                    "section_path": ["Section 1"],
                },
            )
        )

        projector = ProjectionProjector(db_session)
        projector.record_and_apply(
            _make_document_event(
                "ev_publish_only",
                "PublishCompleted",
                doc_id,
                40,
                {
                    "publish_state": "published",
                },
            )
        )
        db_session.commit()

        projection_before = DocumentProjectionRepository(db_session).get(doc_id)
        assert projection_before is not None
        assert projection_before.source_file_id is None
        assert projection_before.parse_snapshot_id is None
        assert projection_before.chunk_count == 0

        reconciler = ProjectionReconciler(
            session=db_session,
            intake_client=_UnusedClient(),
            approval_client=_UnusedClient(),
            indexing_client=_UnusedClient(),
        )
        result = asyncio.run(reconciler.reconcile_documents(limit=10))
        assert result["updated"] == 1

        projection = DocumentProjectionRepository(db_session).get(doc_id)
        assert projection is not None
        assert projection.source_file_id == source_file_id
        assert projection.parse_snapshot_id == "ps_001"
    assert projection.upload_id == "upload_001"
    assert projection.filename == "example.txt"
    assert projection.mime_type == "text/plain"
    assert projection.document_state == "ACTIVE"
    assert projection.publish_state == "published"
    assert projection.active_index_version == "v1"
    assert projection.chunk_count == 2
    assert projection.page_count == 3
    assert projection.parser_profile_name == "naive"
