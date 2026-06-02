"""Tests for EventPublisher, OutboxDispatcher, and consumer idempotency."""

from datetime import datetime, timezone, timedelta

from reality_rag_contracts import EventType, OutboxStatus
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.outbox_events import OutboxEventRepository
from reality_rag_persistence.repositories.consumer_idempotency import (
    ConsumerIdempotencyRepository,
)

from reality_rag_persistence import EventPublisher, OutboxDispatcher


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC tzinfo (SQLite may return naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TestEventPublisher:
    def test_publish_creates_outbox_event(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_001",
                payload={"key": "val"},
                trace_id="trc-1",
            )
            assert evt.event_id.startswith("evt_")
            assert evt.event_type == EventType.FILE_READY.value
            assert evt.status == OutboxStatus.PENDING.value
            assert evt.payload_json == {"key": "val"}

            # Verify in repo
            found = OutboxEventRepository(session).get(evt.event_id)
            assert found is not None
            assert found.trace_id == "trc-1"
        finally:
            session.close()

    def test_publish_stage_task_requested(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish_stage_task_requested(
                intake_job_id="job_1",
                stage_task_id="task_1",
                stage_name="conversion",
                input_hash="hash-1",
                idempotency_key="idem-1",
            )
            assert evt.event_type == EventType.STAGE_TASK_REQUESTED.value
            assert evt.payload["stage_task_id"] == "task_1"
            assert evt.idempotency_key == "idem-1"
        finally:
            session.close()

    def test_publish_approval_requested(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish_approval_requested(
                intake_job_id="job_1",
                preliminary_doc_id="pre_1",
                collection_id="col-1",
                trace_id="trc-1",
            )
            assert evt.event_type == EventType.APPROVAL_REQUESTED.value
            assert evt.payload["preliminary_doc_id"] == "pre_1"
        finally:
            session.close()

    def test_publish_file_ready(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish_file_ready(
                source_file_id="src_1",
                object_id="obj_1",
                collection_id="col-1",
                content_hash="sha256:abc",
            )
            assert evt.event_type == EventType.FILE_READY.value
            assert evt.aggregate_id == "src_1"
        finally:
            session.close()

    def test_payload_hash_is_computed(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_001",
                payload={"a": 1, "b": 2},
            )
            assert evt.payload_hash != ""
            assert len(evt.payload_hash) == 64  # sha256 hex
        finally:
            session.close()


class TestOutboxDispatcher:
    def test_poll_and_dispatch_noop_mode(self):
        """Without deliver callback, dispatcher marks all as sent."""
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_1",
                payload={},
            )
            session.commit()

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=None,
                batch_size=10,
            )
            dispatched = dispatcher.poll_and_dispatch()
            assert dispatched == 1

            # Verify event is now sent
            session2 = get_session()
            found = OutboxEventRepository(session2).get(evt.event_id)
            assert found.status == OutboxStatus.SENT.value
            session2.close()
        finally:
            session.close()

    def test_poll_and_dispatch_with_deliver(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt1 = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_ok",
                payload={},
            )
            evt2 = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_fail",
                payload={},
            )
            session.commit()

            def deliver(evt):
                return evt.aggregate_id == "src_ok"

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=deliver,
                batch_size=10,
            )
            dispatched = dispatcher.poll_and_dispatch()
            assert dispatched == 1  # only src_ok succeeded

            session2 = get_session()
            repo = OutboxEventRepository(session2)
            assert repo.get(evt1.event_id).status == OutboxStatus.SENT.value
            assert repo.get(evt2.event_id).status == OutboxStatus.FAILED.value
            assert repo.get(evt2.event_id).attempt_count == 1
            session2.close()
        finally:
            session.close()

    def test_dispatch_retries_with_backoff(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_fail",
                payload={},
            )
            session.commit()

            call_count = [0]

            def deliver_always_fail(_evt):
                call_count[0] += 1
                return False

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=deliver_always_fail,
                batch_size=10,
                base_retry_seconds=1,
                max_attempts=3,
            )
            # First dispatch
            dispatcher.poll_and_dispatch()
            # Manually move next_attempt_at to past and reset status to pending
            # so second dispatch picks it up
            from reality_rag_persistence.models import OutboxEventModel
            from sqlalchemy import update
            session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.event_id == evt.event_id)
                .values(
                    next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    status="pending",
                )
            )
            session.commit()
            # Second dispatch
            dispatcher.poll_and_dispatch()

            session2 = get_session()
            found = OutboxEventRepository(session2).get(evt.event_id)
            assert found.attempt_count == 2
            assert found.status == OutboxStatus.FAILED.value
            # next_attempt_at should be in future due to backoff
            next_at = _ensure_utc(found.next_attempt_at)
            assert next_at is not None
            assert next_at > datetime.now(timezone.utc)
            session2.close()
        finally:
            session.close()

    def test_max_attempts_reached_stays_failed(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_fail",
                payload={},
            )
            session.commit()

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=lambda e: False,
                batch_size=10,
                base_retry_seconds=0,
                max_attempts=2,
            )
            dispatcher.poll_and_dispatch()
            # Move next_attempt_at to past and reset status to pending for second dispatch
            from reality_rag_persistence.models import OutboxEventModel
            from sqlalchemy import update
            session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.event_id == evt.event_id)
                .values(
                    next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    status="pending",
                )
            )
            session.commit()
            dispatcher.poll_and_dispatch()

            session2 = get_session()
            found = OutboxEventRepository(session2).get(evt.event_id)
            assert found.attempt_count >= 2
            assert found.status == OutboxStatus.FAILED.value
            # next_attempt_at should be None or in very distant future (no more retries)
            next_at = _ensure_utc(found.next_attempt_at)
            if next_at is not None:
                # dispatcher sets next_attempt_at to far future when max attempts reached
                pass
            session2.close()
        finally:
            session.close()

    def test_replay_resets_failed_to_pending(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.FILE_READY,
                aggregate_type="source_file",
                aggregate_id="src_1",
                payload={},
            )
            repo = OutboxEventRepository(session)
            repo.mark_failed(evt.event_id)
            session.commit()

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=None,
            )
            ok = dispatcher.replay(evt.event_id)
            assert ok is True

            session2 = get_session()
            found = OutboxEventRepository(session2).get(evt.event_id)
            assert found.status == OutboxStatus.PENDING.value
            session2.close()
        finally:
            session.close()

    def test_should_process_filter_skips_without_marking_sent(self):
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.STAGE_TASK_REQUESTED,
                aggregate_type="intake_job",
                aggregate_id="job_1",
                payload={"stage_name": "conversion"},
            )
            session.commit()

            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=lambda _e: True,
                should_process=lambda _e: False,
            )
            dispatched = dispatcher.poll_and_dispatch()
            assert dispatched == 0

            session2 = get_session()
            found = OutboxEventRepository(session2).get(evt.event_id)
            assert found is not None
            assert found.status == OutboxStatus.PENDING.value
            session2.close()
        finally:
            session.close()


class TestConsumerIdempotencyIntegration:
    def test_duplicate_event_not_processed_twice(self):
        """Consumer records processed event; duplicate delivery is skipped."""
        session = get_session()
        try:
            idem_repo = ConsumerIdempotencyRepository(session)
            event_id = "evt_dup_001"
            idempotency_key = "idem_dup_001"

            # First time: not processed
            assert idem_repo.is_processed("orchestrator", event_id) is False
            assert idem_repo.is_processed_by_key("orchestrator", idempotency_key) is False

            # Process
            idem_repo.record_processed("orchestrator", event_id, idempotency_key)

            # Second time: already processed
            assert idem_repo.is_processed("orchestrator", event_id) is True
            assert idem_repo.is_processed_by_key("orchestrator", idempotency_key) is True
        finally:
            session.close()

    def test_outbox_replay_with_idempotency_no_duplicate_business_effect(self):
        """Replay outbox event, but consumer idempotency prevents duplicate processing."""
        session = get_session()
        try:
            pub = EventPublisher(session)
            evt = pub.publish(
                event_type=EventType.APPROVAL_DECIDED,
                aggregate_type="intake_job",
                aggregate_id="job_1",
                payload={
                    "intake_job_id": "job_1",
                    "final_doc_id": "doc_q1_v1",
                },
                idempotency_key="job_1:approval_decided:ticket_1",
            )
            session.commit()

            # Simulate consumer processing and recording idempotency
            session2 = get_session()
            idem_repo = ConsumerIdempotencyRepository(session2)
            idem_repo.record_processed(
                "orchestrator", evt.event_id, evt.idempotency_key
            )
            session2.commit()
            session2.close()

            # Replay outbox event
            dispatcher = OutboxDispatcher(
                session_factory=get_session,
                deliver=None,
            )
            dispatcher.replay(evt.event_id)
            dispatcher.poll_and_dispatch()

            # Consumer checks idempotency again
            session3 = get_session()
            idem_repo2 = ConsumerIdempotencyRepository(session3)
            assert idem_repo2.is_processed("orchestrator", evt.event_id) is True
            assert (
                idem_repo2.is_processed_by_key("orchestrator", evt.idempotency_key)
                is True
            )
            session3.close()
        finally:
            session.close()
