"""Tests for task projection."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import _make_token
from workbench_api.projections.projector import ProjectionProjector
from workbench_api.projections.repository import TaskProjectionRepository


class TestTaskProjection:
    def test_list_tasks(self, client: TestClient, uploader_token: str):
        # Create an upload first
        client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        resp = client.get("/workbench/tasks", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_task(self, client: TestClient, uploader_token: str):
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]
        resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_id"] == upload_id
        assert "status" in data
        assert "progress_pct" in data

    def test_task_status_derived(self, client: TestClient, uploader_token: str):
        import respx
        from httpx import Response
        with respx.mock:
            # Mock intake so upload creation succeeds
            respx.post("http://localhost:8003/internal/source-files").mock(
                return_value=Response(200, json={"source_file_id": "sf_001"})
            )
            create_resp = client.post(
                "/workbench/uploads",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "collection_id": "col_default",
                    "filename": "test.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                },
            )
        upload_id = create_resp.json()["upload_id"]
        resp = client.get(f"/workbench/tasks/{upload_id}", headers={"Authorization": f"Bearer {uploader_token}"})
        data = resp.json()
        # Projection should have initial status from upload
        assert data["status"] == "uploading"
        assert data["progress_pct"] == 0


class TestTaskProjectionSQL:
    """Tests that verify list/get read from SQL projection, not downstream fan-out."""

    def test_projection_created_on_upload(self, client: TestClient, uploader_token: str, db_session: Session):
        """Upload should automatically create a projection row."""
        import respx
        from httpx import Response
        with respx.mock:
            respx.post("http://localhost:8003/internal/source-files").mock(
                return_value=Response(200, json={"source_file_id": "sf_001"})
            )
            create_resp = client.post(
                "/workbench/uploads",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "collection_id": "col_default",
                    "filename": "test.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                },
            )
        upload_id = create_resp.json()["upload_id"]

        repo = TaskProjectionRepository(db_session)
        proj = repo.get_by_upload_id(upload_id)
        assert proj is not None
        assert proj.upload_id == upload_id
        assert proj.overall_status == "uploading"
        assert proj.filename == "test.pdf"

    def test_list_reads_from_projection_not_downstream(self, client: TestClient, uploader_token: str, db_session: Session):
        """list_tasks should return projection rows even if downstream is unreachable."""
        import respx
        from httpx import Response
        with respx.mock:
            respx.post("http://localhost:8003/internal/source-files").mock(
                return_value=Response(200, json={"source_file_id": "sf_001"})
            )
            client.post(
                "/workbench/uploads",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "collection_id": "col_default",
                    "filename": "downstream-off.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                },
            )
        # No downstream mocks needed — list should read SQL only
        resp = client.get("/workbench/tasks", headers={"Authorization": f"Bearer {uploader_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        items = [i for i in data["items"] if i["filename"] == "downstream-off.pdf"]
        assert len(items) == 1
        assert items[0]["status"] == "uploading"

    def test_projection_updated_on_content_upload(self, client: TestClient, uploader_token: str, db_session: Session):
        """After content upload, projection should reflect updated status."""
        import respx
        from httpx import Response
        with respx.mock:
            respx.post("http://localhost:8003/internal/source-files").mock(
                return_value=Response(200, json={"source_file_id": "sf_001"})
            )
            respx.post("http://localhost:8006/upload").mock(
                return_value=Response(200, json={"status": "uploaded", "source_file_id": "sf_001"})
            )
            create_resp = client.post(
                "/workbench/uploads",
                headers={"Authorization": f"Bearer {uploader_token}"},
                json={
                    "collection_id": "col_default",
                    "filename": "upload-content.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                },
            )
            upload_id = create_resp.json()["upload_id"]

            # Upload content
            from io import BytesIO
            resp = client.post(
                f"/workbench/uploads/{upload_id}/content",
                headers={"Authorization": f"Bearer {uploader_token}"},
                files={"file": ("upload-content.pdf", BytesIO(b"fake pdf content"), "application/pdf")},
            )
            assert resp.status_code == 200

        # Verify projection was updated
        repo = TaskProjectionRepository(db_session)
        proj = repo.get_by_upload_id(upload_id)
        assert proj is not None
        assert proj.overall_status == "uploaded"
        assert proj.progress_pct == 100


class TestProjectionProjector:
    """Tests for ProjectionProjector idempotency and version ordering."""

    def test_record_and_apply_idempotent(self, db_session: Session):
        """Duplicate event_id should be ignored entirely."""
        projector = ProjectionProjector(db_session)
        event = {
            "event_id": "ev_dup_001",
            "event_type": "TASK_CREATED",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "task",
            "aggregate_id": "upload_001",
            "aggregate_version": 1,
            "occurred_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "payload": {
                "projection_id": "upload_001",
                "tenant_id": "tenant_acme",
                "user_id": "user-001",
                "collection_id": "col_default",
                "upload_id": "upload_001",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "overall_status": "uploading",
                "progress_pct": 0,
            },
            "trace_id": "trc_001",
        }

        result1 = projector.record_and_apply(event)
        db_session.commit()
        assert result1["applied"] is True
        assert result1["event_recorded"] is True

        # Same event again
        result2 = projector.record_and_apply(event)
        db_session.commit()
        assert result2["applied"] is False
        assert result2["event_recorded"] is False
        assert result2["reason"] == "duplicate_event_id"

    def test_version_ordering_old_skipped(self, db_session: Session):
        """Older aggregate_version must not overwrite newer projection state."""
        projector = ProjectionProjector(db_session)
        upload_id = "upload_v_001"

        # Version 2: status = "uploaded"
        event_v2 = {
            "event_id": "ev_v2",
            "event_type": "TASK_CONTENT_UPLOADED",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "task",
            "aggregate_id": upload_id,
            "aggregate_version": 2,
            "occurred_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "payload": {
                "projection_id": upload_id,
                "tenant_id": "tenant_acme",
                "user_id": "user-001",
                "collection_id": "col_default",
                "upload_id": upload_id,
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "overall_status": "uploaded",
                "progress_pct": 100,
            },
            "trace_id": "trc_v2",
        }
        result = projector.record_and_apply(event_v2)
        db_session.commit()
        assert result["applied"] is True

        # Version 1: status = "uploading" — should be skipped
        event_v1 = {
            "event_id": "ev_v1",
            "event_type": "TASK_CREATED",
            "tenant_id": "tenant_acme",
            "collection_id": "col_default",
            "aggregate_type": "task",
            "aggregate_id": upload_id,
            "aggregate_version": 1,
            "occurred_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "payload": {
                "projection_id": upload_id,
                "tenant_id": "tenant_acme",
                "user_id": "user-001",
                "collection_id": "col_default",
                "upload_id": upload_id,
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "overall_status": "uploading",
                "progress_pct": 0,
            },
            "trace_id": "trc_v1",
        }
        result = projector.record_and_apply(event_v1)
        db_session.commit()
        assert result["applied"] is False

        # Verify projection still has version 2 state
        repo = TaskProjectionRepository(db_session)
        proj = repo.get_by_upload_id(upload_id)
        assert proj is not None
        assert proj.overall_status == "uploaded"
        assert proj.progress_pct == 100
        assert proj.version == 2


class TestTaskProjectionTenantIsolation:
    def test_list_tasks_filtered_by_tenant(self, client: TestClient, uploader_token: str):
        # Create upload for tenant_acme
        client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "tenant_acme.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )

        # Create token for different tenant
        other_tenant_token = _make_token("user-001", "uploader@example.com", ["uploader"], tenant_id="tenant_other")

        # Other tenant should not see tenant_acme's tasks
        resp = client.get("/workbench/tasks", headers={"Authorization": f"Bearer {other_tenant_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_get_task_cross_tenant_denied(self, client: TestClient, uploader_token: str):
        # Create upload for tenant_acme
        create_resp = client.post(
            "/workbench/uploads",
            headers={"Authorization": f"Bearer {uploader_token}"},
            json={
                "collection_id": "col_default",
                "filename": "test.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
            },
        )
        upload_id = create_resp.json()["upload_id"]

        # Different user trying to access the task
        other_user_token = _make_token("user-999", "other@example.com", ["uploader"], tenant_id="tenant_acme")
        resp = client.get(
            f"/workbench/tasks/{upload_id}",
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        assert resp.status_code == 404
