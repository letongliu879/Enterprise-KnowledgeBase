"""Tests for dashboard aggregation endpoint."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


class TestDashboard:
    """GET /workbench/dashboard"""

    def test_dashboard_empty(self, client: TestClient, uploader_token: str):
        """Fresh DB returns zeroed stats."""
        resp = client.get(
            "/workbench/dashboard",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["today_uploads"] == 0
        assert data["stats"]["pending_review_count"] == 0
        assert data["stats"]["total_documents"] == 0
        assert data["stats"]["stale_ratio"] == 0.0
        assert data["recent_tickets"] == []

    def test_dashboard_with_data(self, client: TestClient, uploader_token: str, db_session):
        """Insert projections and verify dashboard counts."""
        from reality_rag_persistence.models import (
            WorkbenchDocumentProjectionModel,
            WorkbenchTaskProjectionModel,
            WorkbenchTicketProjectionModel,
        )

        tenant = "tenant_acme"
        now = datetime.now(timezone.utc)

        # Tasks created today
        for i in range(3):
            task = WorkbenchTaskProjectionModel(
                projection_id=f"task_{i}",
                tenant_id=tenant,
                user_id="user-001",
                collection_id="col_default",
                upload_id=f"upload_{i}",
                filename=f"doc_{i}.pdf",
                mime_type="application/pdf",
                size_bytes=100,
                created_at=now,
            )
            db_session.add(task)

        # Pending tickets
        for i in range(2):
            ticket = WorkbenchTicketProjectionModel(
                ticket_id=f"ticket_{i}",
                tenant_id=tenant,
                collection_id="col_default",
                state="pending",
                created_at=now - timedelta(hours=i),
            )
            db_session.add(ticket)

        # Total documents
        for i in range(5):
            doc = WorkbenchDocumentProjectionModel(
                doc_id=f"doc_{i}",
                tenant_id=tenant,
                collection_id="col_default",
                filename=f"file_{i}.pdf",
                mime_type="application/pdf",
                is_stale=(i < 2),  # 2 stale out of 5 = 0.4 ratio
            )
            db_session.add(doc)

        db_session.commit()

        resp = client.get(
            "/workbench/dashboard",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["today_uploads"] == 3
        assert data["stats"]["pending_review_count"] == 2
        assert data["stats"]["total_documents"] == 5
        assert data["stats"]["stale_ratio"] == 0.4
        assert len(data["recent_tickets"]) == 2
