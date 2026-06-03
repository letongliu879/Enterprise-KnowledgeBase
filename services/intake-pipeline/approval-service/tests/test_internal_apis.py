"""Tests for approval-service internal owner APIs."""

import pytest
from fastapi.testclient import TestClient

from reality_rag_persistence.database import create_all, drop_all, override_url_for_testing

from approval_service.main import app


@pytest.fixture(autouse=True)
def _db():
    override_url_for_testing("sqlite:///:memory:")
    create_all()
    yield
    drop_all()


@pytest.fixture
def client():
    return TestClient(app)


class TestListTickets:
    def test_list_tickets(self, client: TestClient):
        resp = client.get("/internal/tickets?tenant_id=tenant_acme")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_tickets_filter_by_state(self, client: TestClient):
        resp = client.get("/internal/tickets?tenant_id=tenant_acme&state=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_tickets_tenant_isolation(self, client: TestClient):
        # Create ticket for tenant_acme
        resp = client.post(
            "/internal/approval/auto-approve",
            json={
                "intake_job_id": "job_tenant",
                "preliminary_doc_id": "doc_tenant",
                "collection_id": "col_default",
                "logical_document_id": "ldoc_tenant",
                "version": 1,
            },
        )
        assert resp.status_code == 200

        # tenant_acme should see the ticket
        resp_acme = client.get("/internal/tickets?tenant_id=tenant_acme")
        assert resp_acme.status_code == 200
        data_acme = resp_acme.json()
        assert data_acme["total"] >= 1

        # tenant_other should see no tickets (fail closed)
        resp_other = client.get("/internal/tickets?tenant_id=tenant_other")
        assert resp_other.status_code == 200
        data_other = resp_other.json()
        assert data_other["total"] == 0
        assert len(data_other["items"]) == 0


class TestGetTicket:
    def test_get_ticket_not_found(self, client: TestClient):
        resp = client.get("/internal/tickets/nonexistent")
        assert resp.status_code == 404


class TestDecideTicket:
    def test_decide_ticket_not_found(self, client: TestClient):
        resp = client.post(
            "/internal/tickets/nonexistent/decide",
            json={
                "command_id": "cmd_001",
                "trace_id": "trc_001",
                "idempotency_key": "idem_001",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "target_type": "ticket",
                "target_id": "nonexistent",
                "payload": {"action": "approve"},
            },
        )
        assert resp.status_code == 404

    def test_decide_invalid_action(self, client: TestClient):
        # First create a ticket via auto-approve
        resp = client.post(
            "/internal/approval/auto-approve",
            json={
                "intake_job_id": "job_001",
                "preliminary_doc_id": "doc_001",
                "collection_id": "col_default",
                "logical_document_id": "ldoc_001",
                "version": 1,
            },
        )
        assert resp.status_code == 200
        ticket_id = resp.json()["ticket_id"]

        # Invalid action
        decide_resp = client.post(
            f"/internal/tickets/{ticket_id}/decide",
            json={
                "command_id": "cmd_002",
                "trace_id": "trc_002",
                "idempotency_key": "idem_002",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "target_type": "ticket",
                "target_id": ticket_id,
                "payload": {"action": "invalid"},
            },
        )
        assert decide_resp.status_code == 400


class TestAgentReview:
    def test_get_agent_review_not_found(self, client: TestClient):
        resp = client.get("/internal/tickets/nonexistent/agent-review")
        assert resp.status_code == 404

    def test_get_agent_review_read_only(self, client: TestClient, monkeypatch):
        # Create a ticket first
        resp = client.post(
            "/internal/approval/auto-approve",
            json={
                "intake_job_id": "job_002",
                "preliminary_doc_id": "doc_002",
                "collection_id": "col_default",
                "logical_document_id": "ldoc_002",
                "version": 1,
            },
        )
        assert resp.status_code == 200
        ticket_id = resp.json()["ticket_id"]

        monkeypatch.setattr(
            "approval_service.main._load_review_artifact_payload",
            lambda session, intake_job_id: {
                "review_run_id": "att-1",
                "intake_job_id": intake_job_id,
                "source_file_id": "src-1",
                "parse_snapshot_id": "pss-1",
                "agent_review_ref": "C:/tmp/review.json",
                "artifact_version": "v1",
                "review_model": "deepseek-chat",
                "prompt_version": "v2",
                "artifact_schema_version": "v2",
                "generated_at": "2026-06-03T00:00:00Z",
                "review_context": {
                    "llm_call_records": [{"request_hash": "sha256:req"}]
                },
                "agent_review": {
                    "decision": "request_changes",
                    "confidence": 0.91,
                    "reasons": ["needs update"],
                    "risk_tags": ["policy_gap"],
                    "publish_recommendation": "pending_review",
                    "document_type": "policy",
                    "suggested_authority_level": 5,
                    "detected_pii": [],
                    "diff_summary": "summary",
                    "anchored_findings": [
                        {
                            "finding_id": "finding-1",
                            "source_quote": "quote",
                            "problem_summary": "problem",
                            "severity": "high",
                            "confidence": 0.8,
                        }
                    ],
                },
            },
        )

        review_resp = client.get(f"/internal/tickets/{ticket_id}/agent-review")
        assert review_resp.status_code == 200
        data = review_resp.json()
        assert data["ticket_id"] == ticket_id
        assert data["decision"] == "REQUEST_CHANGES"
        assert data["review_run_id"] == "att-1"
        assert data["source_file_id"] == "src-1"
        assert data["parse_snapshot_id"] == "pss-1"
        assert len(data["anchored_findings"]) == 1
        assert "quality_findings" in data
