"""Tests for ticket comments CRUD endpoints."""

from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import _make_token
from reality_rag_persistence.models import TicketCommentModel
from workbench_api.projections.projector import ProjectionProjector


class TestTicketComments:
    """CRUD for ticket comments."""

    def _create_ticket_projection(
        self,
        db: Session,
        ticket_id: str,
        tenant_id: str = "tenant_acme",
        collection_id: str = "col_default",
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
            },
            "trace_id": f"test:{ticket_id}",
        }
        projector.record_and_apply(event)
        db.commit()

    def _create_comment(
        self,
        db: Session,
        comment_id: str,
        ticket_id: str,
        user_id: str = "user-001",
        content: str = "Test comment",
        tenant_id: str = "tenant_acme",
        collection_id: str = "col_default",
    ):
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        comment = TicketCommentModel(
            comment_id=comment_id,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            user_id=user_id,
            content=content,
            created_at=now,
            updated_at=now,
        )
        db.add(comment)
        db.commit()

    def test_list_ticket_comments_empty(self, client: TestClient, reviewer_token: str, db_session: Session):
        """List comments for a ticket with no comments returns empty list."""
        self._create_ticket_projection(db_session, "ticket_comment_empty")
        resp = client.get(
            "/workbench/tickets/ticket_comment_empty/comments",
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_create_ticket_comment(self, client: TestClient, uploader_token: str, db_session: Session):
        """Create a comment on a ticket returns 201 with comment data."""
        self._create_ticket_projection(db_session, "ticket_comment_create")
        resp = client.post(
            "/workbench/tickets/ticket_comment_create/comments",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={"content": "This is a test comment"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "This is a test comment"
        assert data["ticket_id"] == "ticket_comment_create"
        assert data["user_id"] == "user-001"
        assert "comment_id" in data

    def test_create_comment_empty_content(self, client: TestClient, uploader_token: str, db_session: Session):
        """Create a comment with empty content returns 400."""
        self._create_ticket_projection(db_session, "ticket_comment_empty_content")
        resp = client.post(
            "/workbench/tickets/ticket_comment_empty_content/comments",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={"content": ""},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error_code"] == "BAD_REQUEST"

    def test_update_own_comment(self, client: TestClient, uploader_token: str, db_session: Session):
        """Update own comment returns 200 with updated content."""
        self._create_ticket_projection(db_session, "ticket_comment_update")
        self._create_comment(db_session, "comment_001", "ticket_comment_update", user_id="user-001")

        resp = client.patch(
            "/workbench/comments/comment_001",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={"content": "Updated comment content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Updated comment content"
        assert data["comment_id"] == "comment_001"

    def test_update_others_comment_forbidden(self, client: TestClient, db_session: Session):
        """Update another user's comment returns 403."""
        uploader_token = _make_token("user-001", "uploader@example.com", ["uploader"])
        other_token = _make_token("user-999", "other@example.com", ["uploader"])

        self._create_ticket_projection(db_session, "ticket_comment_forbidden")
        self._create_comment(db_session, "comment_forbidden", "ticket_comment_forbidden", user_id="user-001")

        resp = client.patch(
            "/workbench/comments/comment_forbidden",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"content": "Should not work"},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error_code"] == "FORBIDDEN"

    def test_delete_own_comment(self, client: TestClient, uploader_token: str, db_session: Session):
        """Delete own comment returns 204."""
        self._create_ticket_projection(db_session, "ticket_comment_delete")
        self._create_comment(db_session, "comment_delete", "ticket_comment_delete", user_id="user-001")

        resp = client.delete(
            "/workbench/comments/comment_delete",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 204

        # Verify it's gone from DB
        comment = db_session.query(TicketCommentModel).filter_by(comment_id="comment_delete").first()
        assert comment is None
