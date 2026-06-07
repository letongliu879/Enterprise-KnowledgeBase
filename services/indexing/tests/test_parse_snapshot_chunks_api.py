from __future__ import annotations

from fastapi.testclient import TestClient

from indexing_service.domain import ParseSnapshotRecord
from reality_rag_persistence.database import get_session
from reality_rag_persistence.models import IntakeJobModel


class TestParseSnapshotChunksApi:
    def test_get_parse_snapshot_chunks_returns_canonical_items(self):
        from indexing_service.main import app, repository

        repository.parse_snapshots_by_id.clear()
        snapshot = ParseSnapshotRecord(
            parse_snapshot_id="ps_123",
            request_id="req_123",
            tenant_id="tenant_acme",
            collection_id="col_default",
            source_file_id="sf_123",
            source_binary_ref="blob://sf_123",
            source_filename="expense-policy.md",
            source_suffix="md",
            parser_id="naive",
            parser_backend="ragflow",
            input_hash="sha256:test",
            preview_text="preview",
            upstream_chunks=[
                {
                    "content_with_weight": "Approved expenses require receipts and manager approval.",
                    "doc_type_kwd": "text",
                    "section_path": ["Expense Policy", "Reimbursement"],
                    "page_num_int": [2],
                }
            ],
            outline=[],
            chunk_preview=[],
            warnings=[],
            decision_reason="ok",
        )
        repository.save_parse_snapshot(snapshot)

        client = TestClient(app)
        response = client.get("/internal/parse-snapshots/ps_123/chunks?page=1&page_size=10")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["evidence_id"].startswith("psc_")
        assert item["doc_id"] == "sf_123"
        assert item["content"] == "Approved expenses require receipts and manager approval."
        assert item["section_path"] == ["Expense Policy", "Reimbursement"]
        assert item["page_spans"] == [{"page_from": 2, "page_to": 2}]

    def test_get_parse_snapshot_chunks_prefers_final_doc_id_when_available(self):
        from indexing_service.main import app, repository

        repository.parse_snapshots_by_id.clear()
        snapshot = ParseSnapshotRecord(
            parse_snapshot_id="ps_456",
            request_id="req_456",
            tenant_id="tenant_acme",
            collection_id="col_default",
            source_file_id="sf_456",
            source_binary_ref="blob://sf_456",
            source_filename="expense-policy.md",
            source_suffix="md",
            parser_id="naive",
            parser_backend="ragflow",
            input_hash="sha256:test",
            preview_text="preview",
            upstream_chunks=[
                {
                    "content_with_weight": "Approved expenses require receipts and manager approval.",
                    "doc_type_kwd": "text",
                    "section_path": ["Expense Policy", "Reimbursement"],
                    "page_num_int": [2],
                }
            ],
            outline=[],
            chunk_preview=[],
            warnings=[],
            decision_reason="ok",
        )
        repository.save_parse_snapshot(snapshot)

        session = get_session()
        try:
            session.add(
                IntakeJobModel(
                    intake_job_id="job_456",
                    source_file_id="sf_456",
                    object_id="obj_456",
                    collection_id="col_default",
                    state="published",
                    state_version=1,
                    current_stage="publishing",
                    preliminary_doc_id="doc_final_456",
                    final_doc_id="doc_final_456",
                    trace_id="trace_456",
                )
            )
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/parse-snapshots/ps_456/chunks?page=1&page_size=10")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["doc_id"] == "doc_final_456"
