"""Outbox deliver callbacks for ingestion-worker.

Routes outbox events to orchestrator actions or stage workers.
"""

from __future__ import annotations

import logging
import asyncio
import os
from datetime import datetime, timezone
import httpx
from typing import Any

from reality_rag_contracts import EventType, IndexStatus, IntakeJobState, OutboxEvent, PublishStatus, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.consumer_idempotency import ConsumerIdempotencyRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from intake_runtime.orchestrator import OrchestratorService

from .job_event_flow import apply_approval_decision, apply_stage_completed
from .document_service_client import DocumentServiceClient

logger = logging.getLogger(__name__)

_FILE_READY_CONSUMER_ID = "ingestion-worker:file-ready"
_STAGE_COMPLETED_CONSUMER_ID = "ingestion-worker:stage-completed"
_APPROVAL_EVENT_CONSUMER_ID = "ingestion-worker:approval-event"
_PUBLISH_EVENT_CONSUMER_ID = "ingestion-worker:publish-event"


def _workbench_events_url(service: str) -> str | None:
    base_url = str(
        os.environ.get("WORKBENCH_API_BASE_URL")
        or os.environ.get("WORKBENCH_BASE_URL")
        or ""
    ).rstrip("/")
    if not base_url:
        return None
    return f"{base_url}/internal/events/{service}"


def _workbench_service_key(service: str) -> str:
    return str(os.environ.get(f"WORKBENCH_EVENT_KEY_{service.upper()}", "")).strip()


def _serialize_workbench_native_event(event: OutboxEvent, *, aggregate_version: int) -> dict[str, Any]:
    payload = dict(event.payload_json or {})
    native_event = event.model_dump(mode="json")
    native_event["payload"] = payload
    native_event["tenant_id"] = payload.get("tenant_id", "")
    native_event["collection_id"] = payload.get("collection_id")
    native_event["aggregate_version"] = aggregate_version
    native_event["occurred_at"] = native_event.get("created_at") or native_event.get("sent_at")
    return native_event


def _forward_event_to_workbench(service: str, event: OutboxEvent, *, aggregate_version: int) -> bool:
    native_event = _serialize_workbench_native_event(event, aggregate_version=aggregate_version)
    return _post_native_events_to_workbench(service, [native_event])


def _post_native_events_to_workbench(service: str, native_events: list[dict[str, Any]]) -> bool:
    url = _workbench_events_url(service)
    api_key = _workbench_service_key(service)
    if not url or not api_key:
        return True

    try:
        response = httpx.post(
            url,
            json=native_events,
            headers={"X-Service-Key": api_key},
            timeout=30.0,
        )
    except Exception:
        logger.exception("outbox: failed to forward events to workbench %s", service)
        return False

    if response.status_code >= 400:
        logger.error(
            "outbox: workbench rejected %s events with status %s: %s",
            service,
            response.status_code,
            response.text,
        )
        return False
    try:
        body = response.json()
    except Exception:
        body = {}
    if int(body.get("errors", 0) or 0) > 0:
        logger.error("outbox: workbench reported projection errors for %s events: %s", service, body)
        return False
    return True


def _deliver_approval_event(event: OutboxEvent) -> bool:
    """Forward approval requests or consume approval outcomes."""
    if event.event_type in {EventType.APPROVAL_PENDING.value, EventType.APPROVAL_DECIDED.value}:
        local_success = False
        session = get_session()
        try:
            idem_repo = ConsumerIdempotencyRepository(session)
            if idem_repo.is_processed(_APPROVAL_EVENT_CONSUMER_ID, event.event_id):
                local_success = True
            else:
                intake_job_id = event.payload_json["intake_job_id"]
                orch = OrchestratorService(session)
                from reality_rag_persistence.models import IntakeJobModel
                row = session.get(IntakeJobModel, intake_job_id)
                if row is not None:
                    row.ticket_id = event.payload_json.get("ticket_id")
                    row.final_doc_id = event.payload_json.get("final_doc_id")

                if event.event_type == EventType.APPROVAL_PENDING.value:
                    orch.advance_state(intake_job_id, IntakeJobState.AWAITING_APPROVAL)
                else:
                    apply_approval_decision(orch, intake_job_id, event.payload_json)

                idem_repo.record_processed(
                    _APPROVAL_EVENT_CONSUMER_ID,
                    event.event_id,
                    event.idempotency_key,
                )
                session.commit()
                local_success = True
        except Exception:
            session.rollback()
            logger.exception("outbox: failed to process approval event")
            return False
        finally:
            session.close()

        if not local_success:
            return False
        aggregate_version = int(event.payload_json.get("ticket_event_version") or (1 if event.event_type == EventType.APPROVAL_PENDING.value else 2))
        return _forward_event_to_workbench("approval", event, aggregate_version=aggregate_version)

    remote_url = os.environ.get("APPROVAL_SERVICE_URL", "").rstrip("/") or os.environ.get("APPROVAL_BASE_URL", "").rstrip("/") or None
    if remote_url is None:
        logger.error("outbox: APPROVAL_SERVICE_URL is required for approval owner delivery")
        return False

    import httpx

    try:
        payload = event.payload_json
        publish_status = payload.get("publish_status")
        if publish_status == PublishStatus.PUBLISHED.value:
            path = "/internal/approval/auto-approve"
        elif publish_status == PublishStatus.REJECTED.value:
            path = "/internal/approval/auto-reject"
        else:
            path = "/internal/approval/pending"
        logger.error("DEBUG: httpx type=%s, url=%s", type(httpx).__name__, f"{remote_url}{path}")
        resp = httpx.post(f"{remote_url}{path}", json=payload, timeout=30.0)
        return resp.status_code < 500
    except Exception:
        logger.exception("outbox: failed to forward approval event")
        return False


def _deliver_stage_completed(event: OutboxEvent) -> bool:
    """Handle StageCompleted by letting orchestrator drive the next step."""
    session = get_session()
    try:
        idem_repo = ConsumerIdempotencyRepository(session)
        if idem_repo.is_processed(_STAGE_COMPLETED_CONSUMER_ID, event.event_id):
            return True

        payload = event.payload_json
        intake_job_id = payload["intake_job_id"]
        stage_name = StageName(payload["stage_name"])
        success = bool(payload.get("success"))
        if not success:
            error_message = payload.get("error_message") or payload.get("error_code") or "Stage failed"
            orch = OrchestratorService(session)
            orch.fail_intake_job(intake_job_id, error_message)
            idem_repo.record_processed(
                _STAGE_COMPLETED_CONSUMER_ID,
                event.event_id,
                event.idempotency_key,
            )
            session.commit()
            return True

        orch = OrchestratorService(session)
        job = IntakeJobRepository(session).get(intake_job_id)
        if job is None:
            raise ValueError(f"Intake job not found: {intake_job_id}")

        apply_stage_completed(session, orch, job, stage_name)

        idem_repo.record_processed(
            _STAGE_COMPLETED_CONSUMER_ID,
            event.event_id,
            event.idempotency_key,
        )
        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception("outbox: failed to process stage completed event")
        return False
    finally:
        session.close()


def _deliver_publish_event(event: OutboxEvent) -> bool:
    """Consume publish lifecycle events or forward publish requests.

    Order: 1) indexing, 2) advance state + record idempotency (same tx).
    If indexing fails the job state is NOT advanced and the event will be
    retried by the next poller cycle.
    """
    if event.event_type == EventType.PUBLISH_COMPLETED.value:
        # Step 1: submit to indexing first.
        try:
            _submit_indexing_after_publish(event.payload_json)
        except Exception:
            logger.exception("outbox: indexing failed for publish event %s", event.event_id)
            return False

        # Step 2: advance state and record idempotency atomically.
        session = get_session()
        try:
            idem_repo = ConsumerIdempotencyRepository(session)
            if idem_repo.is_processed(_PUBLISH_EVENT_CONSUMER_ID, event.event_id):
                return True

            intake_job_id = event.payload_json["intake_job_id"]
            orch = OrchestratorService(session)
            from reality_rag_persistence.models import IntakeJobModel

            row = session.get(IntakeJobModel, intake_job_id)
            if row is not None:
                row.final_doc_id = event.payload_json.get("final_doc_id")

            orch.advance_state(intake_job_id, IntakeJobState.PUBLISHED)
            idem_repo.record_processed(
                _PUBLISH_EVENT_CONSUMER_ID,
                event.event_id,
                event.idempotency_key,
            )
            session.commit()
            return True
        except Exception:
            session.rollback()
            logger.exception("outbox: failed to process publish event")
            return False
        finally:
            session.close()

    logger.warning("outbox: unexpected publish event type %s", event.event_type)
    return True


def _run_coroutine_blocking(coro_factory):
    """Run an async coroutine from a sync context, handling nested event loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coro_factory()))
        return future.result()


def _submit_indexing_after_publish(payload: dict[str, Any]) -> None:
    """Submit published document to indexing via async HTTP call."""
    from .indexing_service import get_indexing_service

    intake_job_id = str(payload.get("intake_job_id") or "").strip()
    collection_id = str(payload.get("collection_id") or "").strip()
    index_version = str(payload.get("index_version") or "").strip()
    if not intake_job_id or not collection_id:
        raise ValueError("PublishCompleted payload missing intake_job_id or collection_id")

    async def _run():
        return await get_indexing_service().run_intake_job(
            intake_job_id=intake_job_id,
            collection_id=collection_id,
            index_version=index_version,
            options={"activate_index_version": True},
        )

    _run_coroutine_blocking(_run)


def _mark_document_index_failed(final_doc_id: str) -> None:
    session = get_session()
    try:
        repo = DocumentRepository(session)
        document = repo.get(final_doc_id)
        if document is not None:
            repo.save(document.model_copy(update={"index_status": IndexStatus.FAILED}))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("outbox: failed to mark document index_status=failed")
    finally:
        session.close()


def _deliver_file_ready(event: OutboxEvent) -> bool:
    """Handle FILE_READY by creating intake job and first stage task only."""
    source_file_id = event.payload_json.get("source_file_id") or event.aggregate_id
    if not source_file_id:
        logger.warning("outbox: file ready missing source_file_id")
        return True

    session = get_session()
    try:
        idem_repo = ConsumerIdempotencyRepository(session)
        if idem_repo.is_processed(_FILE_READY_CONSUMER_ID, event.event_id):
            logger.info("outbox: file ready already processed %s", source_file_id)
            return True

        source_file = SourceFileRepository(session).get(source_file_id)
        if source_file is None:
            raise ValueError(f"Source file not found: {source_file_id}")
        if source_file.state.value != "ready":
            logger.info("outbox: file ready ignored because source file is %s", source_file.state.value)
            return True

        existing_job = IntakeJobRepository(session).get_by_source_file_id(source_file_id)
        if existing_job is not None:
            logger.info("outbox: file ready ignored because intake job exists %s", existing_job.intake_job_id)
            idem_repo.record_processed(_FILE_READY_CONSUMER_ID, event.event_id, event.idempotency_key)
            session.commit()
            return True

        orch = OrchestratorService(session)
        intake_job = orch.create_intake_job(
            source_file_id=source_file.source_file_id,
            object_id=source_file.object_id,
            collection_id=source_file.collection_id,
            trace_id=event.trace_id or source_file.upload_id or "",
        )
        claimed = DocumentServiceClient(session).claim(source_file.source_file_id, intake_job.intake_job_id)
        if not claimed:
            raise ValueError(f"Failed to claim source file {source_file.source_file_id}")

        orch.advance_state(intake_job.intake_job_id, IntakeJobState.CONVERSION_QUEUED)
        input_hash = source_file.content_hash or source_file.object_id
        orch.find_or_create_stage_task(
            intake_job.intake_job_id,
            StageName.CONVERSION,
            f"{intake_job.intake_job_id}:conversion:v1:{input_hash}",
            "v1",
            input_hash,
        )
        idem_repo.record_processed(_FILE_READY_CONSUMER_ID, event.event_id, event.idempotency_key)
        session.commit()
        logger.info("outbox: file ready scheduled %s", source_file_id)

        # Notify workbench of the intake job creation so the task projection
        # gets intake_job_id, intake_job_state, and source_file_state immediately.
        # This replaces the generic FileReady forwarding in make_deliver_callback,
        # which would arrive with a lower version and be skipped.
        _post_native_events_to_workbench("intake", [{
            "event_id": f"evt_job_{intake_job.intake_job_id}",
            "event_type": "IntakeJobStateChanged",
            "tenant_id": event.payload_json.get("tenant_id", "default"),
            "collection_id": source_file.collection_id,
            "aggregate_type": "intake_job",
            "aggregate_id": intake_job.intake_job_id,
            "aggregate_version": 25,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "upload_id": source_file.upload_id or source_file.source_file_id,
                "intake_job_id": intake_job.intake_job_id,
                "source_file_id": source_file.source_file_id,
                "source_file_state": source_file.state.value if hasattr(source_file.state, "value") else str(source_file.state),
                "state": IntakeJobState.CONVERSION_QUEUED.value,
                "collection_id": source_file.collection_id,
                "tenant_id": event.payload_json.get("tenant_id", "default"),
            },
            "trace_id": event.trace_id or "",
        }])

        return True
    except Exception:
        session.rollback()
        logger.exception("outbox: file ready processing failed for %s", source_file_id)
        return False
    finally:
        session.close()


def recover_stuck_approvals() -> int:
    """Re-emit ApprovalRequested events for intake jobs stuck at awaiting_approval.

    This handles the case where the approval service was unavailable when the
    original ApprovalRequested event was processed, causing the outbox event
    to be marked as failed/sent but the intake job never progressing.
    """
    session = get_session()
    try:
        orch = OrchestratorService(session)
        from reality_rag_persistence.models import IntakeJobModel
        from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
        import uuid

        repo = IntakeJobRepository(session)
        stuck = (
            session.query(IntakeJobModel)
            .filter(IntakeJobModel.state == IntakeJobState.AWAITING_APPROVAL.value)
            .filter(IntakeJobModel.ticket_id.isnot(None))
            .all()
        )
        recovered = 0
        for row in stuck:
            try:
                orch.request_approval(
                    intake_job_id=row.intake_job_id,
                    preliminary_doc_id=row.preliminary_doc_id or row.final_doc_id or "",
                    collection_id=row.collection_id,
                    publish_status=PublishStatus.PUBLISHED.value,
                    logical_document_id=row.preliminary_doc_id or "",
                    version=1,
                    ticket_id=row.ticket_id,
                    upload_id=getattr(row, "trace_id", "") or "",
                    idempotency_key=f"recover-approval-{row.intake_job_id}-{uuid.uuid4().hex[:8]}",
                )
                recovered += 1
                logger.info("recovered stuck approval for job=%s", row.intake_job_id)
            except Exception:
                logger.exception("recovery failed for approval job=%s", row.intake_job_id)
        if recovered > 0:
            session.commit()
        return recovered
    except Exception:
        session.rollback()
        logger.exception("approval recovery scan failed")
        return 0
    finally:
        session.close()


def make_deliver_callback() -> Any:
    """Factory for the ingestion-worker outbox deliver callback."""

    def deliver(event: OutboxEvent) -> bool:
        handlers = {
            EventType.STAGE_COMPLETED.value: _deliver_stage_completed,
            EventType.APPROVAL_REQUESTED.value: _deliver_approval_event,
            EventType.APPROVAL_DECIDED.value: _deliver_approval_event,
            EventType.APPROVAL_PENDING.value: _deliver_approval_event,
            EventType.PUBLISH_COMPLETED.value: _deliver_publish_event,
            EventType.FILE_READY.value: _deliver_file_ready,
        }
        handler = handlers.get(event.event_type)
        if handler is None:
            logger.warning("outbox: no handler for event type %s", event.event_type)
            return True
        
        success = handler(event)
        if not success:
            return False
        
        # Forward relevant events to workbench for projection updates.
        # FILE_READY is handled directly by _deliver_file_ready which sends
        # a richer IntakeJobStateChanged event with full state.
        if event.event_type in {
            EventType.STAGE_COMPLETED.value,
            EventType.PUBLISH_COMPLETED.value,
        }:
            return _forward_event_to_workbench("intake", event, aggregate_version=1)
        
        return True

    return deliver
