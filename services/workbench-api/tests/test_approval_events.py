from __future__ import annotations

from datetime import datetime, timezone

from workbench_api.events import auth as event_auth
from workbench_api.projections.repository import AgentReviewProjectionRepository, TicketProjectionRepository


class TestApprovalEventIngestion:
    def test_approval_pending_ingests_ticket_and_findings(self, client, db_session, monkeypatch):
        monkeypatch.setitem(event_auth.SERVICE_KEYS, "approval", "approval-test-key")
        response = client.post(
            "/internal/events/approval",
            headers={"X-Service-Key": "approval-test-key"},
            json=[
                {
                    "event_id": "evt_approval_001",
                    "event_type": "ApprovalPending",
                    "aggregate_type": "intake_job",
                    "aggregate_id": "ij_001",
                    "trace_id": "trc_001",
                    "occurred_at": datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                    "payload": {
                        "ticket_id": "ticket_001",
                        "tenant_id": "tenant_acme",
                        "collection_id": "col_default",
                        "state": "pending",
                        "ticket_event_version": 1,
                        "source_file_id": "sf_001",
                        "parse_snapshot_id": "ps_001",
                        "doc_id": "doc_001",
                        "filename": "expense-policy.md",
                        "agent_decision": "request_changes",
                        "agent_finding_count": 1,
                        "agent_blocking_finding_count": 1,
                        "findings": [
                            {
                                "finding_id": "finding_001",
                                "problem_summary": "Needs correction",
                                "source_quote": "Original quote",
                                "severity": "high",
                                "confidence": 0.91,
                                "source_file_id": "sf_001",
                                "parse_snapshot_id": "ps_001",
                                "doc_id": "doc_001",
                            }
                        ],
                    },
                }
            ],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["applied"] == 2
        ticket = TicketProjectionRepository(db_session).get("ticket_001")
        assert ticket is not None
        assert ticket.state == "pending"
        assert ticket.agent_finding_count == 1
        finding = AgentReviewProjectionRepository(db_session).get("finding_001")
        assert finding is not None
        assert finding.source_quote == "Original quote"
        assert finding.parse_snapshot_id == "ps_001"
