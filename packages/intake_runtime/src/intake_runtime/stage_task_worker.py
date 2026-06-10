"""Helpers for owner workers that self-consume StageTaskRequested events."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from reality_rag_contracts import EventType, OutboxEvent, StageName, StageTaskState
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.consumer_idempotency import ConsumerIdempotencyRepository
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

logger = logging.getLogger(__name__)

StageExecuteFn = Callable[[object, str, str, str], bool]


class OrphanedIntakeJobError(ValueError):
    """Raised when a stage task event references an intake job that no longer exists."""


class OrphanedStageTaskError(ValueError):
    """Raised when processing cannot locate the stage task referenced by an event."""


def make_stage_task_filter(stage_name: StageName) -> Callable[[OutboxEvent], bool]:
    def should_process(event: OutboxEvent) -> bool:
        return (
            event.event_type == EventType.STAGE_TASK_REQUESTED.value
            and event.payload_json.get("stage_name") == stage_name.value
        )

    return should_process


def recover_stuck_stage_tasks(stage_name: StageName, worker_id: str, execute: StageExecuteFn) -> int:
    """Scan for stage tasks stuck in RUNNING with expired leases and re-execute.

    This handles the case where a previous worker crashed after starting a task
    but before completing it. The StageTaskRequested event was already marked
    "sent" in the outbox, so the normal poll loop won't pick it up again.

    Returns the number of recovered tasks.
    """
    session = get_session()
    try:
        repo = StageTaskRepository(session)
        stuck = repo.find_stuck_running(stage_name.value)
        recovered = 0
        for task in stuck:
            try:
                ok = execute(session, task.stage_task_id, task.intake_job_id, worker_id)
                if ok:
                    session.commit()
                    recovered += 1
                    logger.info("recovered stuck %s task=%s", stage_name.value, task.stage_task_id)
                else:
                    session.rollback()
            except Exception:
                session.rollback()
                logger.exception("recovery failed for %s task=%s", stage_name.value, task.stage_task_id)
        return recovered
    finally:
        session.close()


def make_stage_task_deliver(
    *,
    stage_name: StageName,
    consumer_id: str,
    worker_id: str,
    execute: StageExecuteFn,
) -> Callable[[OutboxEvent], bool]:
    def _ack_orphaned_task(
        session,
        *,
        consumer_id: str,
        event: OutboxEvent,
        stage_task_id: str | None,
        intake_job_id: str | None,
    ) -> bool:
        if stage_task_id:
            repo = StageTaskRepository(session)
            task = repo.get(stage_task_id)
            if task is not None:
                if task.intake_job_id != intake_job_id:
                    logger.warning(
                        "stage worker refusing to ack orphaned %s task=%s: "
                        "task belongs to intake_job=%s, event claims intake_job=%s",
                        stage_name.value,
                        stage_task_id,
                        task.intake_job_id,
                        intake_job_id,
                    )
                    return False
                repo.update_state(stage_task_id, StageTaskState.FAILED)
                repo.clear_lock(stage_task_id)
                logger.warning(
                    "stage worker marked orphaned %s task=%s intake_job=%s as failed",
                    stage_name.value,
                    stage_task_id,
                    intake_job_id,
                )
        ConsumerIdempotencyRepository(session).record_processed(
            consumer_id,
            event.event_id,
            event.idempotency_key,
        )
        session.commit()
        return True

    def deliver(event: OutboxEvent) -> bool:
        session = get_session()
        try:
            idem_repo = ConsumerIdempotencyRepository(session)
            if idem_repo.is_processed(consumer_id, event.event_id):
                return True

            payload = event.payload_json
            stage_task_id = payload["stage_task_id"]
            intake_job_id = payload["intake_job_id"]
            if IntakeJobRepository(session).get(intake_job_id) is None:
                raise OrphanedIntakeJobError(f"Intake job not found: {intake_job_id}")
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
        except (OrphanedIntakeJobError, OrphanedStageTaskError):
            return _ack_orphaned_task(
                session,
                consumer_id=consumer_id,
                event=event,
                stage_task_id=event.payload_json.get("stage_task_id"),
                intake_job_id=event.payload_json.get("intake_job_id"),
            )
        except ValueError as exc:
            session.rollback()
            logger.exception(
                "stage worker failed %s task=%s",
                stage_name.value,
                event.payload_json.get("stage_task_id"),
            )
            return False
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
