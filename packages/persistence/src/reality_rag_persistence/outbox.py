"""Outbox dispatcher and event publisher.

Outbox pattern guarantees:
  1. Business state and outbox_events are written in the same DB transaction.
  2. Dispatcher polls pending events asynchronously.
  3. Consumer deduplicates by event_id and idempotency_key.
  4. Remote owner unavailability does not block local transaction commit.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable
from uuid import uuid4

from reality_rag_contracts import EventType, OutboxEvent, OutboxStatus

from .repositories.outbox_events import OutboxEventRepository


# ── Event Publisher ─────────────────────────────────────────────────────

class EventPublisher:
    """Publish events by writing to outbox in the same DB transaction.

    This guarantees atomicity: business state + outbox event commit together,
    or both rollback. Remote service unavailability never blocks local commit.
    """

    def __init__(self, session) -> None:
        self._session = session
        self._repo = OutboxEventRepository(session)

    def publish(
        self,
        event_type: EventType,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        trace_id: str = "",
        schema_version: str = "2026-05-21.v1",
    ) -> OutboxEvent:
        """Write an outbox event in the current transaction."""
        event_id = _generate_event_id()
        payload_json = payload
        payload_hash = _hash_payload(payload_json)

        return self._repo.create(
            event_id=event_id,
            event_type=event_type.value,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            schema_version=schema_version,
            payload_json=payload_json,
            payload_hash=payload_hash,
            idempotency_key=idempotency_key,
            trace_id=trace_id or event_id,
        )

    def publish_stage_task_requested(
        self,
        intake_job_id: str,
        stage_task_id: str,
        stage_name: str,
        input_hash: str,
        idempotency_key: str,
        *,
        trace_id: str = "",
    ) -> OutboxEvent:
        return self.publish(
            event_type=EventType.STAGE_TASK_REQUESTED,
            aggregate_type="intake_job",
            aggregate_id=intake_job_id,
            payload={
                "intake_job_id": intake_job_id,
                "stage_task_id": stage_task_id,
                "stage_name": stage_name,
                "input_hash": input_hash,
                "idempotency_key": idempotency_key,
            },
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )

    def publish_stage_completed(
        self,
        intake_job_id: str,
        stage_task_id: str,
        stage_attempt_id: str,
        stage_name: str,
        *,
        success: bool,
        trace_id: str = "",
        **extra: Any,
    ) -> OutboxEvent:
        return self.publish(
            event_type=EventType.STAGE_COMPLETED,
            aggregate_type="intake_job",
            aggregate_id=intake_job_id,
            payload={
                "intake_job_id": intake_job_id,
                "stage_task_id": stage_task_id,
                "stage_attempt_id": stage_attempt_id,
                "stage_name": stage_name,
                "success": success,
                **extra,
            },
            idempotency_key=f"{stage_attempt_id}:stage_completed",
            trace_id=trace_id,
        )

    def publish_approval_requested(
        self,
        intake_job_id: str,
        preliminary_doc_id: str,
        collection_id: str,
        *,
        trace_id: str = "",
        **extra: Any,
    ) -> OutboxEvent:
        return self.publish(
            event_type=EventType.APPROVAL_REQUESTED,
            aggregate_type="intake_job",
            aggregate_id=intake_job_id,
            payload={
                "intake_job_id": intake_job_id,
                "preliminary_doc_id": preliminary_doc_id,
                "collection_id": collection_id,
                **extra,
            },
            trace_id=trace_id,
        )

    def publish_publish_completed(
        self,
        intake_job_id: str,
        final_doc_id: str,
        collection_id: str,
        *,
        trace_id: str = "",
        **extra: Any,
    ) -> OutboxEvent:
        return self.publish(
            event_type=EventType.PUBLISH_COMPLETED,
            aggregate_type="intake_job",
            aggregate_id=intake_job_id,
            payload={
                "intake_job_id": intake_job_id,
                "final_doc_id": final_doc_id,
                "collection_id": collection_id,
                **extra,
            },
            trace_id=trace_id,
        )

    def publish_file_ready(
        self,
        source_file_id: str,
        object_id: str,
        collection_id: str,
        content_hash: str,
        *,
        trace_id: str = "",
        **extra: Any,
    ) -> OutboxEvent:
        return self.publish(
            event_type=EventType.FILE_READY,
            aggregate_type="source_file",
            aggregate_id=source_file_id,
            payload={
                "source_file_id": source_file_id,
                "object_id": object_id,
                "collection_id": collection_id,
                "content_hash": content_hash,
                **extra,
            },
            trace_id=trace_id,
        )


# ── Outbox Dispatcher ───────────────────────────────────────────────────

DeliverCallback = Callable[[OutboxEvent], bool]
EventFilter = Callable[[OutboxEvent], bool]


class OutboxDispatcher:
    """PostgreSQL polling dispatcher for outbox events.

    Runs in a background loop (or triggered by scheduler):
      1. Poll pending events
      2. Call deliver callback for each
      3. Mark sent on success, failed with retry backoff on failure
    """

    def __init__(
        self,
        session_factory: Callable,
        deliver: DeliverCallback | None = None,
        should_process: EventFilter | None = None,
        batch_size: int = 100,
        max_attempts: int = 10,
        base_retry_seconds: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._deliver = deliver
        self._should_process = should_process
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._base_retry_seconds = base_retry_seconds

    def poll_and_dispatch(self) -> int:
        """Poll pending events and dispatch them.

        Returns the number of events dispatched.
        """
        session = self._session_factory()
        try:
            repo = OutboxEventRepository(session)
            pending = repo.list_pending(limit=self._batch_size)
            dispatched = 0
            for event in pending:
                if self._should_process is not None and not self._should_process(event):
                    continue
                if self._dispatch_one(session, repo, event):
                    dispatched += 1
            session.commit()
            return dispatched
        finally:
            session.close()

    def _dispatch_one(
        self,
        session,
        repo: OutboxEventRepository,
        event: OutboxEvent,
    ) -> bool:
        """Dispatch a single event. Returns True if successful."""
        if self._deliver is None:
            # No deliver callback: just mark as sent (noop mode)
            repo.mark_sent(event.event_id)
            return True

        try:
            success = self._deliver(event)
        except Exception:
            success = False

        if success:
            repo.mark_sent(event.event_id)
            return True

        # Failure: schedule retry with exponential backoff
        if event.attempt_count + 1 >= self._max_attempts:
            # Max attempts reached: keep as failed
            repo.mark_failed(event.event_id, next_attempt_at=None)
        else:
            backoff = self._base_retry_seconds * (2 ** event.attempt_count)
            next_attempt = datetime.now(timezone.utc) + timedelta(seconds=backoff)
            repo.mark_failed(event.event_id, next_attempt_at=next_attempt)
        return False

    def replay(self, event_id: str) -> bool:
        """Reset a failed event back to pending for manual replay."""
        session = self._session_factory()
        try:
            repo = OutboxEventRepository(session)
            ok = repo.reset_pending(event_id)
            session.commit()
            return ok
        finally:
            session.close()


# ── Helpers ─────────────────────────────────────────────────────────────
_PREFIX = "evt_"


def _generate_event_id() -> str:
    return _PREFIX + uuid4().hex[:16]


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
