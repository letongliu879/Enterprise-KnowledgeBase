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


class TestProjectionEventSequence:
    """Integration test: full event chain as it flows through the system.

    This test catches version-ordering bugs, missing enum values, and
    status-regression issues that unit tests of individual events miss.
    """

    def test_full_pipeline_status_progression(self, db_session: Session):
        """Simulate complete event chain: upload → scanning → intake → review."""
        upload_id = "upload_chain_001"
        projector = ProjectionProjector(db_session)

        # 1. Frontend creates upload → TASK_CREATED (v=1)
        assert projector.record_and_apply(_make_event(
            "ev_create", "TASK_CREATED", upload_id, 1,
            {"projection_id": upload_id, "upload_id": upload_id,
             "filename": "chain.pdf", "overall_status": "uploading"}
        ))["applied"]
        _check(db_session, upload_id, "uploading", version=1)

        # 2. Upload content completed → TASK_CONTENT_UPLOADED (v=2)
        assert projector.record_and_apply(_make_event(
            "ev_content", "TASK_CONTENT_UPLOADED", upload_id, 2,
            {"projection_id": upload_id, "upload_id": upload_id,
             "source_file_id": "src_chain_001", "overall_status": "ready"}
        ))["applied"]
        _check(db_session, upload_id, "ready", version=2)

        # 3. FileReady from intake adapter (v=20) → sets source_file_state
        assert projector.record_and_apply(_make_event(
            "ev_file_ready", "FileReady", upload_id, 20,
            {"upload_id": upload_id, "source_file_id": "src_chain_001",
             "source_file_state": "ready"}
        ))["applied"]
        # Status should stay "ready" (source_file_state=ready, no intake_job_state yet)
        _check(db_session, upload_id, "ready", version=20)

        # 4. IntakeJobStateChanged from _deliver_file_ready (v=25) → intake job created
        assert projector.record_and_apply(_make_event(
            "ev_job_created", "IntakeJobStateChanged", upload_id, 25,
            {"upload_id": upload_id, "intake_job_id": "job_chain_001",
             "intake_job_state": "conversion_queued"}
        ))["applied"]
        _check(db_session, upload_id, "parsing", version=25)

        # 5. StageCompleted (conversion done) from intake adapter (v=30)
        assert projector.record_and_apply(_make_event(
            "ev_stage_conv", "StageCompleted", upload_id, 30,
            {"upload_id": upload_id, "intake_job_state": "processing"}
        ))["applied"]
        _check(db_session, upload_id, "parsing", version=30)

        # 6. StageCompleted (agent review done) (v=30 again, should be skipped)
        # Since v=30 already applied, another v=30 event should be skipped.
        result = projector.record_and_apply(_make_event(
            "ev_stage_review", "StageCompleted", upload_id, 30,
            {"upload_id": upload_id, "intake_job_state": "review_running"}
        ))
        assert result["applied"] is False  # skipped by version check

        # 7. StageCompleted at higher version (v=31) should be accepted
        # (simulating StageCompleted being re-sent with a proper unique version)
        assert projector.record_and_apply(_make_event(
            "ev_stage_review_v31", "StageCompleted", upload_id, 31,
            {"upload_id": upload_id, "intake_job_state": "review_running"}
        ))["applied"]
        _check(db_session, upload_id, "reviewing", version=31)

    def test_derived_status_all_states(self, db_session: Session):
        """_derive_overall_status must recognize all intake_job_state values."""
        projector = ProjectionProjector(db_session)
        # Helper: apply event with given intake_job_state and check derived status
        def check_derived(intake_state: str, expected: str) -> None:
            uid = f"upload_derive_{intake_state}"
            projector.record_and_apply(_make_event(
                f"ev_{intake_state}", "IntakeJobStateChanged", uid, 25,
                {"upload_id": uid, "intake_job_id": "job_x",
                 "intake_job_state": intake_state, "source_file_state": "ready"}
            ))
            proj = TaskProjectionRepository(db_session).get_by_upload_id(uid)
            assert proj.overall_status == expected, \
                f"intake_job_state={intake_state} → expected {expected}, got {proj.overall_status}"

        check_derived("created", "parsing")
        check_derived("conversion_queued", "parsing")
        check_derived("conversion_running", "parsing")
        check_derived("parsing", "parsing")
        check_derived("processing", "parsing")   # StageCompleted sends this
        check_derived("failed", "failed")
        check_derived("review_queued", "reviewing")
        check_derived("review_running", "reviewing")
        check_derived("review_succeeded", "reviewing")
        check_derived("approval_requested", "reviewing")
        check_derived("awaiting_approval", "reviewing")
        check_derived("publish_queued", "publishing")
        check_derived("publish_running", "publishing")
        check_derived("published", "published")


def _make_event(event_id: str, event_type: str, upload_id: str, version: int,
                payload: dict) -> dict:
    from datetime import datetime, timezone
    return {
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": "tenant_acme",
        "collection_id": "col_default",
        "aggregate_type": "task",
        "aggregate_id": upload_id,
        "aggregate_version": version,
        "occurred_at": datetime.now(timezone.utc),
        "payload": payload,
        "trace_id": upload_id,
    }


def _check(db_session, upload_id: str, expected_status: str, version: int):
    proj = TaskProjectionRepository(db_session).get_by_upload_id(upload_id)
    assert proj is not None
    assert proj.overall_status == expected_status, \
        f"v{version}: expected {expected_status}, got {proj.overall_status}"
    assert proj.version == version, \
        f"expected version {version}, got {proj.version}"


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
