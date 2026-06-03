"""Tests for tickets — projection-based reads.

List endpoints read from SQL projection only.
Detail endpoints read projection first, with approval fallback.
"""

from datetime import datetime, timezone

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from conftest import _make_token
from workbench_api.projections.projector import ProjectionProjector


class TestTicketsProjection:
    """Ticket list tests — must read from projection, not downstream."""

    def _create_ticket_projection(
        self,
        db: Session,
        ticket_id: str,
        tenant_id: str = "tenant_acme",
        collection_id: str = "col_default",
        state: str = "pending",
        title: str = "Test Ticket",
    ):
        """Helper to create a ticket projection row directly."""
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_{ticket_id}",
            "event_type": "TicketCreated",
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "aggregate_type": "ticket",
            "aggregate_id": ticket_id,
            "aggregate_version": 1,
            "occurred_at": datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "ticket_id": ticket_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "state": state,
                "title": title,
            },
            "trace_id": "test",
        }
        projector.record_and_apply(event)
        db.commit()

    def test_list_tickets_reads_projection(self, client: TestClient, reviewer_token: str, db_session: Session):
        self._create_ticket_projection(db_session, "ticket_123")
        resp = client.get(
            "/workbench/tickets",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["ticket_id"] == "ticket_123"
        assert data["items"][0]["status"] == "pending"

    def test_list_tickets_filters_inaccessible_collections(self, client: TestClient, db_session: Session):
        self._create_ticket_projection(db_session, "ticket_123", collection_id="col_default")
        self._create_ticket_projection(db_session, "ticket_999", collection_id="col_secret")

        restricted_token = _make_token(
            "user-003",
            "reviewer@example.com",
            ["reviewer"],
            allowed_collections=["col_default"],
        )
        resp = client.get(
            "/workbench/tickets",
            headers={"Authorization": f"Bearer {restricted_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert [item["ticket_id"] for item in data["items"]] == ["ticket_123"]

    def test_list_tickets_zero_downstream_calls(self, client: TestClient, reviewer_token: str, db_session: Session):
        """Verify that listing tickets does NOT call approval service."""
        self._create_ticket_projection(db_session, "ticket_123")
        # No respx.mock here — if any downstream call happens, it would fail
        resp = client.get(
            "/workbench/tickets",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_tickets_pagination(self, client: TestClient, reviewer_token: str, db_session: Session):
        for i in range(5):
            self._create_ticket_projection(db_session, f"ticket_{i}")

        resp = client.get(
            "/workbench/tickets?page=1&page_size=2",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_list_tickets_state_filter(self, client: TestClient, reviewer_token: str, db_session: Session):
        self._create_ticket_projection(db_session, "ticket_pending", state="pending")
        self._create_ticket_projection(db_session, "ticket_approved", state="approved")

        resp = client.get(
            "/workbench/tickets?state=approved",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["ticket_id"] == "ticket_approved"

    def test_list_tickets_unauthorized(self, client: TestClient):
        resp = client.get("/workbench/tickets")
        assert resp.status_code == 401


class TestTicketsDetail:
    """Ticket detail tests — projection first, then approval fallback."""

    def _create_ticket_projection(self, db: Session, ticket_id: str, state: str = "pending", is_stale: bool = False):
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_{ticket_id}",
            "event_type": "TicketCreated",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "ticket",
            "aggregate_id": ticket_id,
            "aggregate_version": 1,
            "occurred_at": datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "ticket_id": ticket_id,
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "state": state,
                "title": "Test Ticket",
            },
            "trace_id": "test",
        }
        projector.record_and_apply(event)
        if is_stale:
            from workbench_api.projections.repository import TicketProjectionRepository
            repo = TicketProjectionRepository(db)
            repo.mark_stale(ticket_id, "test_stale")
        db.commit()

    def test_get_ticket_from_projection(self, client: TestClient, reviewer_token: str, db_session: Session):
        self._create_ticket_projection(db_session, "ticket_123")
        resp = client.get(
            "/workbench/tickets/ticket_123",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket_id"] == "ticket_123"
        assert data["source"] == "projection"

    def test_get_ticket_fallback_to_approval(self, client: TestClient, reviewer_token: str, db_session: Session):
        """When projection is stale, fallback to approval service."""
        self._create_ticket_projection(db_session, "ticket_123", is_stale=True)
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "status": "PENDING",
                    "doc_id": "doc_123",
                    "source_file_id": "sf_123",
                    "created_at": "2026-05-27T10:00:00Z",
                }
            )
            resp = client.get(
                "/workbench/tickets/ticket_123",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ticket_id"] == "ticket_123"
            assert data["source"] == "approval"

    def test_get_ticket_not_found(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/nonexistent").respond(404)
            resp = client.get(
                "/workbench/tickets/nonexistent",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
        # ApprovalClient maps 404 to DOWNSTREAM_NOT_IMPLEMENTED (501)
        assert resp.status_code == 501


class TestTicketsDecide:
    """Ticket decision still calls approval service."""

    def test_decide_ticket_requires_reviewer(self, client: TestClient, uploader_token: str):
        resp = client.post(
            "/workbench/tickets/ticket_123/decide",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "decision_request_id": "dec_123",
                "action": "APPROVE",
                "actor": "user-001",
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "FORBIDDEN"

    def test_decide_ticket(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "tenant_id": "tenant_acme",
                    "status": "PENDING",
                }
            )
            decide_route = respx.post("http://localhost:8004/internal/tickets/ticket_123/decide").mock(
                return_value=Response(200, json={"status": "APPROVED", "ticket_id": "ticket_123"})
            )
            resp = client.post(
                "/workbench/tickets/ticket_123/decide",
                headers={"Authorization": f"Bearer {reviewer_token}"},
                json={
                    "decision_request_id": "dec_123",
                    "action": "APPROVE",
                    "actor": "user-003",
                    "tenant_id": "tenant_wrong",
                    "collection_id": "col_wrong",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["decision"] == "APPROVE"
            sent = decide_route.calls[0].request.read().decode("utf-8")
            assert '"tenant_id":"tenant_acme"' in sent
            assert '"collection_id":"col_default"' in sent
            assert '"actor":"user-003"' in sent


class TestAgentReviewProjection:
    """Agent review reads from projection first."""

    def _create_finding(self, db: Session, ticket_id: str, finding_id: str):
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_finding_{finding_id}",
            "event_type": "AgentReviewCompleted",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "agent_review",
            "aggregate_id": finding_id,
            "aggregate_version": 1,
            "occurred_at": datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "finding_id": finding_id,
                "tenant_id": "tenant_acme",
                "collection_id": "col_default",
                "ticket_id": ticket_id,
                "severity": "high",
                "category": "factual_error",
                "problem_summary": "Test finding",
                "source_quote": "Quoted source text",
                "parse_snapshot_id": "ps_123",
                "source_file_id": "sf_123",
                "confidence": 0.95,
                "state": "open",
            },
            "trace_id": "test",
        }
        projector.record_and_apply(event)
        db.commit()

    def test_get_agent_review_from_projection(self, client: TestClient, reviewer_token: str, db_session: Session):
        self._create_finding(db_session, "ticket_123", "finding_001")
        resp = client.get(
            "/workbench/tickets/ticket_123/agent-review",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "projection"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["finding_id"] == "finding_001"
        assert data["findings"][0]["source_quote"] == "Quoted source text"
        assert data["parse_snapshot_id"] == "ps_123"

    def test_get_agent_review_fallback(self, client: TestClient, reviewer_token: str):
        """When no projection findings exist, fallback to approval service."""
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                }
            )
            respx.get("http://localhost:8004/internal/tickets/ticket_123/agent-review").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "decision": "REQUEST_CHANGES",
                    "source_file_id": "sf_123",
                    "parse_snapshot_id": "ps_123",
                    "findings": [
                        {
                            "finding_id": "finding_001",
                            "severity": "high",
                            "category": "",
                            "problem_summary": "Needs correction",
                            "source_quote": "Quoted source text",
                            "state": "open",
                            "confidence": 0.92,
                        }
                    ],
                    "matched_count": 0,
                    "unmatched_count": 1,
                }
            )
            resp = client.get(
                "/workbench/tickets/ticket_123/agent-review",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "approval"
            assert data["decision"] == "REQUEST_CHANGES"
            assert data["findings"][0]["source_quote"] == "Quoted source text"
