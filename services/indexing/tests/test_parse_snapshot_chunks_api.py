from __future__ import annotations

from fastapi.testclient import TestClient

from indexing_service.domain import ParseSnapshotRecord


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
