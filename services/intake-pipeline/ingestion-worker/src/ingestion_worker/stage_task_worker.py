"""Helpers for owner workers that self-consume StageTaskRequested events."""

from __future__ import annotations

import logging
from collections.abc import Callable

from reality_rag_contracts import EventType, OutboxEvent, StageName
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.consumer_idempotency import ConsumerIdempotencyRepository

logger = logging.getLogger(__name__)

StageExecuteFn = Callable[[object, str, str, str], bool]


def make_stage_task_filter(stage_name: StageName) -> Callable[[OutboxEvent], bool]:
    def should_process(event: OutboxEvent) -> bool:
        return (
            event.event_type == EventType.STAGE_TASK_REQUESTED.value
            and event.payload_json.get("stage_name") == stage_name.value
        )

    return should_process


def make_stage_task_deliver(
    *,
    stage_name: StageName,
    consumer_id: str,
    worker_id: str,
    execute: StageExecuteFn,
) -> Callable[[OutboxEvent], bool]:
    def deliver(event: OutboxEvent) -> bool:
        session = get_session()
        try:
            idem_repo = ConsumerIdempotencyRepository(session)
            if idem_repo.is_processed(consumer_id, event.event_id):
                return True

            payload = event.payload_json
            stage_task_id = payload["stage_task_id"]
            intake_job_id = payload["intake_job_id"]
            if not execute(session, stage_task_id, intake_job_id, worker_id):
                session.rollback()
                return False

            idem_repo.record_processed(
                consumer_id,
                event.event_id,
                event.idempotency_key,
            )
            session.commit()
            logger.info(
                "stage worker processed %s task=%s intake_job=%s",
                stage_name.value,
                stage_task_id,
                intake_job_id,
            )
            return True
        except Exception:
            session.rollback()
            logger.exception(
                "stage worker failed %s task=%s",
                stage_name.value,
                event.payload_json.get("stage_task_id"),
            )
            return False
        finally:
            session.close()

    return deliver
