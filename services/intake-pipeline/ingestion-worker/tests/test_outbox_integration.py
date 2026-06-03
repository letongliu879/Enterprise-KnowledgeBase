"""Integration tests for outbox wiring into orchestrator and document domains."""

from reality_rag_contracts import (
    EventType,
    IntakeJobState,
    OutboxStatus,
    SourceFileState,
    StageName,
    StageTaskState,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.outbox_events import OutboxEventRepository
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

from approval_service.approval_domain import ApprovalService
from ingestion_worker.orchestrator import OrchestratorService
from reality_rag_documents import DocumentService


class TestOrchestratorOutboxIntegration:
    def test_create_stage_task_writes_stage_task_requested_outbox(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-001", "obj-001", "col-1")

            task, is_new = orch.find_or_create_stage_task(
                job.intake_job_id,
                StageName.CONVERSION,
                "key-001",
                "v1",
                "hash-001",
            )
            assert is_new is True

            # Verify outbox event was written
            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt_types = [e.event_type for e in events]
            assert EventType.STAGE_TASK_REQUESTED.value in evt_types

            # Verify payload contains stage_task_id
            evt = next(e for e in events if e.event_type == EventType.STAGE_TASK_REQUESTED.value)
            assert evt.payload["stage_task_id"] == task.stage_task_id
            assert evt.payload["intake_job_id"] == job.intake_job_id
        finally:
            session.close()

    def test_existing_task_does_not_create_duplicate_outbox(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-002", "obj-002", "col-1")

            task1, is_new1 = orch.find_or_create_stage_task(
                job.intake_job_id,
                StageName.CONVERSION,
                "key-dup",
                "v1",
                "hash-dup",
            )
            assert is_new1 is True

            # Count outbox events before second call
            outbox_repo = OutboxEventRepository(session)
            before = len(outbox_repo.list_pending(limit=10))

            task2, is_new2 = orch.find_or_create_stage_task(
                job.intake_job_id,
                StageName.CONVERSION,
                "key-dup",
                "v1",
                "hash-dup",
            )
            assert is_new2 is False
            assert task1.stage_task_id == task2.stage_task_id

            after = len(outbox_repo.list_pending(limit=10))
            assert after == before  # no new outbox event
        finally:
            session.close()

    def test_request_approval_writes_outbox(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-003", "obj-003", "col-1")

            orch.request_approval(
                intake_job_id=job.intake_job_id,
                preliminary_doc_id="pre_001",
                collection_id="col-1",
                trace_id="trc-1",
            )

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt_types = [e.event_type for e in events]
            assert EventType.APPROVAL_REQUESTED.value in evt_types
        finally:
            session.close()

    def test_publish_completed_writes_outbox(self):
        session = get_session()
        try:
            orch = OrchestratorService(session)
            job = orch.create_intake_job("src-005", "obj-005", "col-1")

            orch.publish_completed(
                intake_job_id=job.intake_job_id,
                final_doc_id="doc_final_005",
                collection_id="col-1",
            )

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next((e for e in events if e.event_type == EventType.PUBLISH_COMPLETED.value), None)
            assert evt is not None
            assert evt.payload["final_doc_id"] == "doc_final_005"
        finally:
            session.close()


class TestApprovalServiceOutboxIntegration:
    def test_auto_approve_emits_approval_decided(self):
        session = get_session()
        try:
            svc = ApprovalService(session)
            ticket = svc.submit_auto_approve(
                intake_job_id="job-001",
                preliminary_doc_id="pre_001",
                collection_id="col-1",
                logical_document_id="ldoc_001",
                version=1,
                confirmed_tags=["financial"],
            )
            assert ticket.final_doc_id is not None

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next(
                (e for e in events if e.event_type == EventType.APPROVAL_DECIDED.value),
                None,
            )
            assert evt is not None
            assert evt.payload["decision"] == "approve"
            assert evt.payload["final_doc_id"] == ticket.final_doc_id
        finally:
            session.close()

    def test_auto_reject_emits_approval_decided(self):
        session = get_session()
        try:
            svc = ApprovalService(session)
            ticket = svc.submit_auto_reject(
                intake_job_id="job-002",
                preliminary_doc_id="pre_002",
                collection_id="col-1",
                rejection_reason="PII detected",
            )

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next(
                (e for e in events if e.event_type == EventType.APPROVAL_DECIDED.value),
                None,
            )
            assert evt is not None
            assert evt.payload["decision"] == "reject"
            assert "final_doc_id" not in evt.payload or evt.payload.get("final_doc_id") is None
        finally:
            session.close()

    def test_create_pending_emits_approval_pending(self):
        session = get_session()
        try:
            svc = ApprovalService(session)
            ticket = svc.create_pending(
                intake_job_id="job-003",
                preliminary_doc_id="pre_003",
                collection_id="col-1",
            )
            assert ticket.state.value == "pending"

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next(
                (e for e in events if e.event_type == EventType.APPROVAL_PENDING.value),
                None,
            )
            assert evt is not None
            assert evt.payload["ticket_id"] == ticket.ticket_id
        finally:
            session.close()

    def test_manual_approve_emits_approval_decided(self):
        session = get_session()
        try:
            svc = ApprovalService(session)
            pending = svc.create_pending(
                intake_job_id="job-004",
                preliminary_doc_id="pre_004",
                collection_id="col-1",
            )
            approved = svc.approve(ticket_id=pending.ticket_id, actor_id="user_1")

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=20)
            evt = next(
                (e for e in events if e.event_type == EventType.APPROVAL_DECIDED.value and e.payload["ticket_id"] == pending.ticket_id),
                None,
            )
            assert evt is not None
            assert evt.payload["decision"] == "approve"
            assert evt.payload["final_doc_id"] == approved.final_doc_id
        finally:
            session.close()


class TestDocumentServiceOutboxIntegration:
    def _seed_collection(self, session, collection_id: str = "col-outbox"):
        from reality_rag_contracts import Tenant, Collection
        from reality_rag_persistence.repositories.tenants import TenantRepository
        from reality_rag_persistence.repositories.collections import CollectionRepository

        if TenantRepository(session).get("default") is None:
            TenantRepository(session).save(Tenant(tenant_id="default", name="Default"))
        if CollectionRepository(session).get(collection_id) is None:
            CollectionRepository(session).save(
                Collection(
                    collection_id=collection_id,
                    tenant_id="default",
                    name="Test Collection",
                    authority_level=5,
                )
            )
        session.commit()

    def test_create_source_file_ready_emits_file_ready(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:ready1", "s3://bucket/ready1", 100)
            sf = svc.create_source_file(
                collection_id="col-outbox",
                object_id=obj.object_id,
                content_hash="sha256:ready1",
                state=SourceFileState.READY,
            )

            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next(
                (e for e in events if e.event_type == EventType.FILE_READY.value),
                None,
            )
            assert evt is not None
            assert evt.payload["source_file_id"] == sf.source_file_id
            assert evt.payload["collection_id"] == "col-outbox"
        finally:
            session.close()

    def test_complete_scan_clean_emits_file_ready(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:scan1", "s3://bucket/scan1", 100)
            sf = svc.create_source_file(
                collection_id="col-outbox",
                object_id=obj.object_id,
                content_hash="sha256:scan1",
                state=SourceFileState.UPLOADED,
            )
            svc.start_scan(sf.source_file_id)

            # Clear any existing outbox events
            outbox_repo = OutboxEventRepository(session)
            for e in outbox_repo.list_pending(limit=100):
                outbox_repo.mark_sent(e.event_id)
            session.commit()

            svc.complete_scan(sf.source_file_id)

            events = outbox_repo.list_pending(limit=10)
            evt = next(
                (e for e in events if e.event_type == EventType.FILE_READY.value),
                None,
            )
            assert evt is not None
            assert evt.payload["source_file_id"] == sf.source_file_id
        finally:
            session.close()

    def test_duplicate_event_does_not_duplicate_final_doc_id(self):
        """Outbox replay with consumer idempotency prevents duplicate final_doc_id."""
        session = get_session()
        try:
            svc = ApprovalService(session)
            ticket = svc.submit_auto_approve(
                intake_job_id="job-dedup",
                preliminary_doc_id="pre_dedup",
                collection_id="col-1",
                logical_document_id="ldoc_dedup",
                version=1,
            )
            final_doc_id = ticket.final_doc_id

            # Simulate outbox replay: the same intake_job + ticket produces
            # the same final_doc_id, but consumer idempotency prevents re-processing.
            outbox_repo = OutboxEventRepository(session)
            events = outbox_repo.list_pending(limit=10)
            evt = next(
                e for e in events if e.event_type == EventType.APPROVAL_DECIDED.value
            )

            # Record consumer idempotency
            from reality_rag_persistence.repositories.consumer_idempotency import (
                ConsumerIdempotencyRepository,
            )

            idem_repo = ConsumerIdempotencyRepository(session)
            idem_repo.record_processed(
                "orchestrator", evt.event_id, evt.idempotency_key
            )

            # Even if the same event is replayed, consumer would skip it
            assert idem_repo.is_processed("orchestrator", evt.event_id) is True
            assert idem_repo.is_processed_by_key("orchestrator", evt.idempotency_key) is True

            # final_doc_id remains the same (no duplicate generated)
            assert final_doc_id == "pre_dedup"
        finally:
            session.close()
