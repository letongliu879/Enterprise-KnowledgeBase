"""Tests for Phase 7 outbox deliver callbacks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from reality_rag_contracts import EventType, IntakeJobState, OutboxEvent, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.models import IntakeJobModel, SourceFileModel, StageResultModel
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.consumer_idempotency import ConsumerIdempotencyRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.tenants import TenantRepository
from reality_rag_contracts import Collection, Tenant, SourceFileState

from ingestion_worker.outbox_deliver import make_deliver_callback


class TestOutboxDeliverCallbacks:
    def _make_event(self, event_type: EventType, aggregate_id: str = "test-1", payload: dict | None = None) -> OutboxEvent:
        return OutboxEvent(
            event_id="evt_test",
            event_type=event_type.value,
            aggregate_type="test",
            aggregate_id=aggregate_id,
            schema_version="v1",
            payload_json=payload or {},
            payload_hash="sha256:abc",
            status="pending",
            attempt_count=0,
        )

    def test_stage_task_requested_missing_payload_returns_false(self):
        deliver = make_deliver_callback()
        evt = self._make_event(EventType.STAGE_TASK_REQUESTED)
        assert deliver(evt) is True

    def test_file_ready_schedules_intake_job(self, inprocess_document_owner):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            if TenantRepository(session).get("default") is None:
                TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
            if CollectionRepository(session).get("col-1") is None:
                CollectionRepository(session).save(
                    Collection(
                        collection_id="col-1",
                        tenant_id="default",
                        name="Test Collection",
                        authority_level=5,
                    )
                )
            ObjectBlobRepository(session).create(
                object_id="obj-test-ready-1",
                content_hash="sha256:test-ready-1",
                storage_key=__file__,
                size_bytes=1,
            )
            SourceFileRepository(session).create(
                source_file_id="src-ready-1",
                collection_id="col-1",
                object_id="obj-test-ready-1",
                content_hash="sha256:test-ready-1",
                state=SourceFileState.READY,
            )
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.FILE_READY,
            aggregate_id="src-ready-1",
            payload={"source_file_id": "src-ready-1"},
        )
        assert deliver(evt) is True

        session = get_session()
        try:
            assert ConsumerIdempotencyRepository(session).is_processed(
                "ingestion-worker:file-ready",
                evt.event_id,
            )
            from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
            intake_job = IntakeJobRepository(session).get_by_source_file_id("src-ready-1")
            assert intake_job is not None
        finally:
            session.close()

    def test_file_ready_duplicate_event_is_idempotent(self, inprocess_document_owner):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            if TenantRepository(session).get("default") is None:
                TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
            if CollectionRepository(session).get("col-1") is None:
                CollectionRepository(session).save(
                    Collection(
                        collection_id="col-1",
                        tenant_id="default",
                        name="Test Collection",
                        authority_level=5,
                    )
                )
            ObjectBlobRepository(session).create(
                object_id="obj-test-ready-2",
                content_hash="sha256:test-ready-2",
                storage_key=__file__,
                size_bytes=1,
            )
            SourceFileRepository(session).create(
                source_file_id="src-ready-2",
                collection_id="col-1",
                object_id="obj-test-ready-2",
                content_hash="sha256:test-ready-2",
                state=SourceFileState.READY,
            )
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.FILE_READY,
            aggregate_id="src-ready-2",
            payload={"source_file_id": "src-ready-2"},
        )
        assert deliver(evt) is True
        assert deliver(evt) is True

    def test_unknown_event_type_returns_true(self):
        deliver = make_deliver_callback()
        evt = self._make_event(EventType.STAGE_TASK_REQUESTED)
        evt.event_type = "unknown_event"
        assert deliver(evt) is True

    def test_approval_event_remote_mode_forwards_http(self, monkeypatch):
        monkeypatch.setenv("APPROVAL_SERVICE_URL", "http://approval:8000")
        deliver = make_deliver_callback()
        evt = self._make_event(
            EventType.APPROVAL_REQUESTED,
            payload={
                "intake_job_id": "job-1",
                "preliminary_doc_id": "doc-1",
                "collection_id": "col-1",
                "publish_status": "published",
                "logical_document_id": "logical-1",
                "version": 1,
                "confirmed_tags": [],
            },
        )
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 200
            assert deliver(evt) is True
            mock_post.assert_called_once_with(
                "http://approval:8000/internal/approval/auto-approve",
                json=evt.payload_json,
                timeout=30.0,
            )

    def test_approval_event_remote_mode_failure_returns_false(self, monkeypatch):
        monkeypatch.setenv("APPROVAL_SERVICE_URL", "http://approval:8000")
        deliver = make_deliver_callback()
        evt = self._make_event(EventType.APPROVAL_DECIDED)
        with patch("httpx.post") as mock_post:
            mock_post.return_value.status_code = 503
            assert deliver(evt) is False

    def test_approval_pending_moves_job_to_awaiting_approval(self):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            from intake_runtime.orchestrator import OrchestratorService

            job = OrchestratorService(session).create_intake_job("src-appr", "obj-appr", "col-1")
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.APPROVAL_PENDING,
            aggregate_id=job.intake_job_id,
            payload={"intake_job_id": job.intake_job_id, "ticket_id": "t-pending"},
        )
        assert deliver(evt) is True

        session = get_session()
        try:
            from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository

            refreshed = IntakeJobRepository(session).get(job.intake_job_id)
            assert refreshed is not None
            assert refreshed.state == IntakeJobState.AWAITING_APPROVAL.value
        finally:
            session.close()

    def test_approval_pending_forwards_event_to_workbench(self):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            from intake_runtime.orchestrator import OrchestratorService

            job = OrchestratorService(session).create_intake_job("src-appr-fwd", "obj-appr-fwd", "col-1")
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.APPROVAL_PENDING,
            aggregate_id=job.intake_job_id,
            payload={
                "intake_job_id": job.intake_job_id,
                "ticket_id": "t-pending",
                "tenant_id": "tenant_acme",
                "collection_id": "col-1",
                "state": "pending",
                "ticket_event_version": 1,
            },
        )
        with patch.dict(
            "os.environ",
            {
                "WORKBENCH_API_BASE_URL": "http://workbench:18083",
                "WORKBENCH_EVENT_KEY_APPROVAL": "approval-secret",
            },
            clear=False,
        ):
            with patch("httpx.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.text = "ok"
                mock_post.return_value.json.return_value = {"errors": 0}
                assert deliver(evt) is True
                assert mock_post.call_args.args[0] == "http://workbench:18083/internal/events/approval"
                assert mock_post.call_args.kwargs["headers"]["X-Service-Key"] == "approval-secret"
                forwarded = mock_post.call_args.kwargs["json"][0]
                assert forwarded["event_type"] == EventType.APPROVAL_PENDING.value
                assert forwarded["aggregate_version"] == 1
                assert forwarded["payload"]["ticket_id"] == "t-pending"

    def test_stage_completed_conversion_marks_consumed_and_queues_review(self, inprocess_document_owner):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            from intake_runtime.orchestrator import OrchestratorService

            if TenantRepository(session).get("default") is None:
                TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
            if CollectionRepository(session).get("col-1") is None:
                CollectionRepository(session).save(
                    Collection(
                        collection_id="col-1",
                        tenant_id="default",
                        name="Test Collection",
                        authority_level=5,
                    )
                )
            ObjectBlobRepository(session).create(
                object_id="obj-stage-complete-1",
                content_hash="sha256:stage-complete-1",
                storage_key=__file__,
                size_bytes=1,
            )
            SourceFileRepository(session).create(
                source_file_id="src-stage-complete-1",
                collection_id="col-1",
                object_id="obj-stage-complete-1",
                content_hash="sha256:stage-complete-1",
                state=SourceFileState.READY,
            )
            job = OrchestratorService(session).create_intake_job(
                "src-stage-complete-1",
                "obj-stage-complete-1",
                "col-1",
            )
            SourceFileRepository(session).claim("src-stage-complete-1", job.intake_job_id)
            session.add(
                StageResultModel(
                    stage_result_id="res-conv-1",
                    stage_task_id="task-conv-1",
                    stage_attempt_id="att-conv-1",
                    intake_job_id=job.intake_job_id,
                    stage_name=StageName.CONVERSION.value,
                    idempotency_key="conv:key",
                    result_hash="hash:conv",
                    summary_json={
                        "preliminary_doc_id": "pre-doc-1",
                        "logical_document_id": "logical-1",
                        "version": 1,
                        "conversion_result": {
                            "source_file_path": __file__,
                            "conversion_status": "success",
                            "doc_id": "pre-doc-1",
                            "canonical_asset_path": "",
                            "canonical_md": "",
                            "error_message": "",
                            "warnings": [],
                            "metadata": {},
                        },
                        "quality_report": {
                            "doc_id": "pre-doc-1",
                            "recommended_review_status": "published",
                            "blocking_reasons": [],
                        },
                    },
                )
            )
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.STAGE_COMPLETED,
            aggregate_id=job.intake_job_id,
            payload={
                "intake_job_id": job.intake_job_id,
                "stage_task_id": "task-conv-1",
                "stage_attempt_id": "att-conv-1",
                "stage_name": StageName.CONVERSION.value,
                "success": True,
            },
        )
        assert deliver(evt) is True

        session = get_session()
        try:
            from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
            from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

            refreshed = IntakeJobRepository(session).get(job.intake_job_id)
            source_file = SourceFileRepository(session).get("src-stage-complete-1")
            tasks = StageTaskRepository(session).list_by_intake_job(job.intake_job_id)
            assert refreshed is not None
            assert refreshed.state == IntakeJobState.REVIEW_QUEUED.value
            assert refreshed.preliminary_doc_id == "pre-doc-1"
            assert source_file is not None
            assert source_file.state == SourceFileState.CONSUMED
            assert any(task.stage_name == StageName.AGENT_REVIEW.value for task in tasks)
        finally:
            session.close()

    def test_stage_completed_publishing_marks_job_published_and_cleanable(self, inprocess_document_owner):
        deliver = make_deliver_callback()
        session = get_session()
        try:
            from intake_runtime.orchestrator import OrchestratorService

            if TenantRepository(session).get("default") is None:
                TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
            if CollectionRepository(session).get("col-1") is None:
                CollectionRepository(session).save(
                    Collection(
                        collection_id="col-1",
                        tenant_id="default",
                        name="Test Collection",
                        authority_level=5,
                    )
                )
            ObjectBlobRepository(session).create(
                object_id="obj-stage-complete-pub-1",
                content_hash="sha256:stage-complete-pub-1",
                storage_key=__file__,
                size_bytes=1,
            )
            SourceFileRepository(session).create(
                source_file_id="src-stage-complete-pub-1",
                collection_id="col-1",
                object_id="obj-stage-complete-pub-1",
                content_hash="sha256:stage-complete-pub-1",
                state=SourceFileState.CONSUMED,
            )
            job = OrchestratorService(session).create_intake_job(
                "src-stage-complete-pub-1",
                "obj-stage-complete-pub-1",
                "col-1",
            )
            source_row = session.get(SourceFileModel, "src-stage-complete-pub-1")
            assert source_row is not None
            source_row.claimed_by_job_id = job.intake_job_id
            row = session.get(IntakeJobModel, job.intake_job_id)
            assert row is not None
            row.final_doc_id = "doc-pub-1"
            row.state = IntakeJobState.PUBLISH_RUNNING.value
            session.add(
                StageResultModel(
                    stage_result_id="res-pub-1",
                    stage_task_id="task-pub-1",
                    stage_attempt_id="att-pub-1",
                    intake_job_id=job.intake_job_id,
                    stage_name=StageName.PUBLISHING.value,
                    idempotency_key="pub:key",
                    result_hash="hash:pub",
                    summary_json={
                        "schema_version": "v1",
                        "input_hash": "pub-input",
                        "result_hash": "pub-result",
                        "asset_paths": {"canonical_md": "x.md"},
                        "asset_bundle": {
                            "doc_id": "doc-pub-1",
                            "collection_id": "col-1",
                            "index_version": "v1",
                            "canonical_source": "x.md",
                            "chunks": [],
                            "opensearch_records": [],
                            "qdrant_points": [],
                        },
                        "canonical_metadata": {
                            "tenant_id": "default",
                            "collection_id": "col-1",
                            "doc_id": "doc-pub-1",
                            "logical_document_id": "logical-pub-1",
                            "source_hash": "sha256:stage-complete-pub-1",
                            "source_content_hash": "sha256:stage-complete-pub-1",
                            "version": 1,
                            "archived": False,
                            "publish_status": "published",
                            "index_status": "indexing",
                            "authority_level": 3,
                            "governance_level": "standard",
                            "access_policy": "collection_default",
                            "domain_tags": [],
                            "risk_tags": [],
                            "quality_summary": "",
                            "processing_summary": "",
                            "asset_paths": {"index_version": "v1"},
                        },
                        "document_persisted": True,
                        "policy_persisted": True,
                    },
                )
            )
            session.commit()
        finally:
            session.close()

        evt = self._make_event(
            EventType.STAGE_COMPLETED,
            aggregate_id=job.intake_job_id,
            payload={
                "intake_job_id": job.intake_job_id,
                "stage_task_id": "task-pub-1",
                "stage_attempt_id": "att-pub-1",
                "stage_name": StageName.PUBLISHING.value,
                "success": True,
            },
        )
        assert deliver(evt) is True

        session = get_session()
        try:
            from reality_rag_persistence.models import OutboxEventModel

            source_file = SourceFileRepository(session).get("src-stage-complete-pub-1")
            publish_event = (
                session.query(OutboxEventModel)
                .filter(OutboxEventModel.aggregate_id == job.intake_job_id)
                .filter(OutboxEventModel.event_type == EventType.PUBLISH_COMPLETED.value)
                .first()
            )
            assert source_file is not None
            assert source_file.state == SourceFileState.CLEANABLE
            assert publish_event is not None
        finally:
            session.close()
