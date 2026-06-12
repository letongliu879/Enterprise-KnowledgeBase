"""Tests for ticket transfer endpoint."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from workbench_api.projections.projector import ProjectionProjector


class TestTicketTransfer:
    """POST /workbench/tickets/{ticket_id}/transfer"""

    def _create_ticket_projection(
        self,
        db: Session,
        ticket_id: str,
        tenant_id: str = "tenant_acme",
        collection_id: str = "col_default",
        assignee_user_id: str | None = "user-001",
    ):
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_tkt_{ticket_id}",
            "event_type": "TicketCreated",
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "aggregate_type": "ticket",
            "aggregate_id": ticket_id,
            "aggregate_version": 1,
            "occurred_at": datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "ticket_id": ticket_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "state": "pending",
                "title": "Test Ticket",
                "assignee_user_id": assignee_user_id,
            },
            "trace_id": f"test:{ticket_id}",
        }
        projector.record_and_apply(event)
        db.commit()

    def test_transfer_ticket_success(self, client: TestClient, reviewer_token: str, db_session: Session):
        """Transfer a ticket to another user returns 200 with updated assignee."""
        self._create_ticket_projection(db_session, "ticket_transfer_001", assignee_user_id="user-003")

        resp = client.post(
            "/workbench/tickets/ticket_transfer_001/transfer",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"assignee_user_id": "user-999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket_id"] == "ticket_transfer_001"
        assert data["assignee_user_id"] == "user-999"

    def test_transfer_self_forbidden(self, client: TestClient, reviewer_token: str, db_session: Session):
        """Transferring a ticket to yourself returns 400."""
        self._create_ticket_projection(db_session, "ticket_transfer_self", assignee_user_id="user-003")

        resp = client.post(
            "/workbench/tickets/ticket_transfer_self/transfer",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"assignee_user_id": "user-003"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error_code"] == "BAD_REQUEST"

    def test_transfer_ticket_not_found(self, client: TestClient, reviewer_token: str):
        """Transfer a non-existent ticket returns 404."""
        resp = client.post(
            "/workbench/tickets/nonexistent/transfer",
            headers={"Authorization": f"Bearer {reviewer_token}"},
            json={"assignee_user_id": "user-999"},
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error_code"] == "NOT_FOUND"
