from __future__ import annotations

from datetime import datetime, timezone

from workbench_api.config import config
from workbench_api.events.adapters.intake_adapter import IntakeEventAdapter
from workbench_api.events.adapters.approval_adapter import ApprovalEventAdapter
from workbench_api.projections.repository import AgentReviewProjectionRepository, TicketProjectionRepository


class TestApprovalEventIngestion:
    def test_approval_pending_ingests_ticket_and_findings(self, client, db_session, monkeypatch):
        monkeypatch.setattr(config, "workbench_event_key_approval", "approval-test-key")
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

    def test_agent_review_event_id_is_bounded(self):
        adapter = ApprovalEventAdapter()
        events = adapter.adapt(
            {
                "event_id": "evt_approval_very_long_identifier_001",
                "event_type": "ApprovalDecided",
                "occurred_at": datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                "payload": {
                    "ticket_id": "ticket_001",
                    "tenant_id": "tenant_acme",
                    "collection_id": "col_default",
                    "findings": [
                        {
                            "finding_id": "8ec77ae30446b6818baff54e75c826d3b7fcd665a457ef13dbcb27d3bffd4f4c",
                            "problem_summary": "Needs correction",
                        }
                    ],
                },
            }
        )
        finding_event = next(event for event in events if event.aggregate_type == "agent_review")
        assert len(finding_event.event_id) <= 64

    def test_intake_adapter_falls_back_to_default_tenant(self):
        adapter = IntakeEventAdapter()
        events = adapter.adapt(
            {
                "event_id": "evt_intake_001",
                "event_type": "StageCompleted",
                "tenant_id": "",
                "collection_id": "col_default",
                "occurred_at": datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                "payload": {
                    "upload_id": "upload_001",
                },
            }
        )
        assert len(events) == 1
        assert events[0].tenant_id == "default"
