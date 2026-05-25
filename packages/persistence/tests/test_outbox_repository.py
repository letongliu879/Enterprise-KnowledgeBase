"""Tests for OutboxEventRepository and ConsumerIdempotencyRepository."""

from datetime import datetime, timezone, timedelta

from reality_rag_contracts import OutboxStatus, EventType
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.consumer_idempotency import (
    ConsumerIdempotencyRepository,
)
from reality_rag_persistence.repositories.outbox_events import OutboxEventRepository


class TestOutboxEventRepository:
    def test_create_and_get(self):
        session = get_session()
        try:
            repo = OutboxEventRepository(session)
            evt = repo.create(
                event_id="evt_001",
                event_type=EventType.FILE_READY.value,
                aggregate_type="source_file",
                aggregate_id="src_001",
                payload_json={"key": "val"},
                payload_hash="abc",
                idempotency_key="idem-1",
                trace_id="trc-1",
            )
            assert evt.event_id == "evt_001"
            assert evt.status == OutboxStatus.PENDING.value

            found = repo.get("evt_001")
            assert found is not None
            assert found.event_type == EventType.FILE_READY.value
        finally:
            session.close()

    def test_list_pending_filters_by_status_and_next_attempt(self):
        session = get_session()
        try:
            repo = OutboxEventRepository(session)
            now = datetime.now(timezone.utc)

            # pending, next_attempt in past
            repo.create(
                event_id="evt_past",
                event_type=EventType.STAGE_TASK_REQUESTED.value,
                aggregate_type="intake_job",
                aggregate_id="job_1",
                payload_json={},
                next_attempt_at=now - timedelta(seconds=10),
            )
            # pending, next_attempt in future
            repo.create(
                event_id="evt_future",
                event_type=EventType.STAGE_TASK_REQUESTED.value,
                aggregate_type="intake_job",
                aggregate_id="job_2",
                payload_json={},
                next_attempt_at=now + timedelta(seconds=60),
            )
            # sent
            repo.create(
                event_id="evt_sent",
                event_type=EventType.STAGE_TASK_REQUESTED.value,
                aggregate_type="intake_job",
                aggregate_id="job_3",
                payload_json={},
                next_attempt_at=now - timedelta(seconds=10),
            )
            repo.mark_sent("evt_sent")

            pending = repo.list_pending(limit=10)
            ids = {e.event_id for e in pending}
            assert "evt_past" in ids
            assert "evt_future" not in ids
            assert "evt_sent" not in ids
        finally:
            session.close()

    def test_mark_sent(self):
        session = get_session()
        try:
            repo = OutboxEventRepository(session)
            repo.create(
                event_id="evt_sent_test",
                event_type=EventType.FILE_READY.value,
                aggregate_type="source_file",
                aggregate_id="src_1",
                payload_json={},
            )
            ok = repo.mark_sent("evt_sent_test")
            assert ok is True

            evt = repo.get("evt_sent_test")
            assert evt.status == OutboxStatus.SENT.value
            assert evt.sent_at is not None
        finally:
            session.close()

    def test_mark_failed_with_retry(self):
        session = get_session()
        try:
            repo = OutboxEventRepository(session)
            repo.create(
                event_id="evt_fail",
                event_type=EventType.FILE_READY.value,
                aggregate_type="source_file",
                aggregate_id="src_1",
                payload_json={},
            )
            next_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            ok = repo.mark_failed("evt_fail", next_attempt_at=next_at)
            assert ok is True

            evt = repo.get("evt_fail")
            assert evt.status == OutboxStatus.FAILED.value
            assert evt.attempt_count == 1
            assert evt.next_attempt_at is not None
        finally:
            session.close()

    def test_reset_pending_for_replay(self):
        session = get_session()
        try:
            repo = OutboxEventRepository(session)
            repo.create(
                event_id="evt_replay",
                event_type=EventType.FILE_READY.value,
                aggregate_type="source_file",
                aggregate_id="src_1",
                payload_json={},
            )
            repo.mark_failed("evt_replay")
            assert repo.get("evt_replay").status == OutboxStatus.FAILED.value

            ok = repo.reset_pending("evt_replay")
            assert ok is True
            assert repo.get("evt_replay").status == OutboxStatus.PENDING.value
        finally:
            session.close()


class TestConsumerIdempotencyRepository:
    def test_record_and_check(self):
        session = get_session()
        try:
            repo = ConsumerIdempotencyRepository(session)
            repo.record_processed("orchestrator", "evt_001", "idem-1")

            assert repo.is_processed("orchestrator", "evt_001") is True
            assert repo.is_processed("orchestrator", "evt_002") is False
            assert repo.is_processed("other_consumer", "evt_001") is False
        finally:
            session.close()

    def test_is_processed_by_key(self):
        session = get_session()
        try:
            repo = ConsumerIdempotencyRepository(session)
            repo.record_processed("orchestrator", "evt_001", "idem-1")

            assert repo.is_processed_by_key("orchestrator", "idem-1") is True
            assert repo.is_processed_by_key("orchestrator", "idem-2") is False
            assert repo.is_processed_by_key("other_consumer", "idem-1") is False
        finally:
            session.close()

    def test_empty_key_returns_false(self):
        session = get_session()
        try:
            repo = ConsumerIdempotencyRepository(session)
            assert repo.is_processed_by_key("orchestrator", "") is False
            assert repo.is_processed_by_key("orchestrator", None) is False  # type: ignore[arg-type]
        finally:
            session.close()
