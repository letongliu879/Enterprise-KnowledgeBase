from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from workbench_api.projections.projector import ProjectionProjector
from workbench_api.projections.reconciler import ProjectionReconciler
from workbench_api.projections.repository import AgentReviewProjectionRepository


class _UnusedClient:
    pass


class _FakeIndexingClient:
    async def get_parse_snapshot_chunks(self, parse_snapshot_id: str, page: int = 1, page_size: int = 50):
        assert parse_snapshot_id == "ps_001"
        return {
            "items": [
                {
                    "evidence_id": "psc_match_001",
                    "content": "Expense policy requires manager approval and original receipts for reimbursement.",
                    "section_path": ["Expense Policy", "Reimbursement"],
                    "page_spans": [{"page_from": 2, "page_to": 2}],
                    "page_from": 2,
                    "page_to": 2,
                },
                {
                    "evidence_id": "psc_other_002",
                    "content": "Office supplies below fifty dollars are auto approved.",
                    "section_path": ["Expense Policy", "Supplies"],
                    "page_spans": [{"page_from": 3, "page_to": 3}],
                    "page_from": 3,
                    "page_to": 3,
                },
            ],
            "total": 2,
        }


class TestAgentReviewMatcher:
    def test_reconcile_agent_reviews_backfills_match(self, db_session):
        projector = ProjectionProjector(db_session)
        projector.record_and_apply(
            {
                "event_id": "ev_finding_match_001",
                "event_type": "approval_pending",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "aggregate_type": "agent_review",
                "aggregate_id": "finding_match_001",
                "aggregate_version": 1,
                "occurred_at": datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc),
                "payload": {
                    "finding_id": "finding_match_001",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "ticket_id": "ticket_001",
                    "doc_id": "doc_001",
                    "source_file_id": "sf_001",
                    "parse_snapshot_id": "ps_001",
                    "severity": "high",
                    "category": "",
                    "problem_summary": "Missing approval requirement",
                    "source_quote": "Manager approval and original receipts are required for reimbursement.",
                    "confidence": 0.94,
                    "state": "open",
                },
                "trace_id": "trc_match_001",
            }
        )
        db_session.commit()

        reconciler = ProjectionReconciler(
            session=db_session,
            intake_client=_UnusedClient(),
            approval_client=_UnusedClient(),
            indexing_client=_FakeIndexingClient(),
        )
        result = asyncio.run(reconciler.reconcile_agent_reviews(limit=10))
        assert result["updated"] == 1

        finding = AgentReviewProjectionRepository(db_session).get("finding_match_001")
        assert finding is not None
        assert finding.evidence_id == "psc_match_001"
        assert finding.page_from == 2
        assert finding.page_to == 2
        assert "manager approval" in (finding.chunk_quote or "").lower()
