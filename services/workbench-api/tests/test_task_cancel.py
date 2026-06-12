"""Tests for task cancel endpoint."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from workbench_api.projections.projector import ProjectionProjector


class TestTaskCancel:
    """POST /workbench/tasks/{upload_id}/cancel"""

    def _create_task_projection(
        self,
        db: Session,
        upload_id: str,
        user_id: str = "user-001",
        tenant_id: str = "tenant_acme",
        collection_id: str = "col_default",
        overall_status: str = "uploading",
        **kwargs,
    ):
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_{upload_id}",
            "event_type": "UploadCreated",
            "tenant_id": tenant_id,
            "collection_id": collection_id,
            "aggregate_type": "task",
            "aggregate_id": upload_id,
            "aggregate_version": 1,
            "occurred_at": datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "projection_id": upload_id,
                "upload_id": upload_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "filename": kwargs.get("filename", "test.pdf"),
                "mime_type": kwargs.get("mime_type", "application/pdf"),
                "size_bytes": kwargs.get("size_bytes", 1024),
                "overall_status": overall_status,
            },
            "trace_id": f"test:{upload_id}",
        }
        projector.record_and_apply(event)
        db.commit()

    def _finalise_task(self, db: Session, upload_id: str, status: str = "completed"):
        """Move a task to a terminal state via an event."""
        projector = ProjectionProjector(db)
        event = {
            "event_id": f"ev_{upload_id}_final",
            "event_type": "StatusChanged",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "task",
            "aggregate_id": upload_id,
            "aggregate_version": 2,
            "occurred_at": datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc),
            "payload": {
                "projection_id": upload_id,
                "upload_id": upload_id,
                "overall_status": status,
            },
            "trace_id": f"test:{upload_id}",
        }
        projector.record_and_apply(event)
        db.commit()

    def test_cancel_task_success(self, client: TestClient, uploader_token: str, db_session: Session):
        """Cancel a task in non-terminal state returns 200 and cancelled status."""
        self._create_task_projection(db_session, "upload_cancel_001")

        resp = client.post(
            "/workbench/tasks/upload_cancel_001/cancel",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["task_id"] == "upload_cancel_001"

    def test_cancel_task_not_found(self, client: TestClient, uploader_token: str):
        """Cancel a non-existent task returns 404."""
        resp = client.post(
            "/workbench/tasks/nonexistent/cancel",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error_code"] == "NOT_FOUND"

    def test_cancel_task_already_final(self, client: TestClient, uploader_token: str, db_session: Session):
        """Cancel a task in a terminal state returns 409."""
        self._create_task_projection(db_session, "upload_cancel_002", overall_status="uploading")
        self._finalise_task(db_session, "upload_cancel_002", "completed")

        resp = client.post(
            "/workbench/tasks/upload_cancel_002/cancel",
            headers={"Authorization": f"Bearer {uploader_token}"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["error_code"] == "CONFLICT"
