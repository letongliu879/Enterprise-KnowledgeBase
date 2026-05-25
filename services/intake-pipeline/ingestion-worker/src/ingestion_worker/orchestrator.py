"""Orchestrator service — manages intake job and stage lifecycle.

Phase 2: Single-process orchestrator that records state into persistent tables.
Even though stages still run in-process, only this module may write to
intake_jobs, stage_tasks, stage_attempts, stage_results.

Idempotency rules:
  - Same idempotency_key + succeeded -> return existing result
  - Same idempotency_key + failed -> create new attempt under same task
  - Different input_hash -> always new stage_task
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from reality_rag_contracts import (
    IntakeJob,
    IntakeJobState,
    StageAttempt,
    StageAttemptState,
    StageName,
    StageResult,
    StageTask,
    StageTaskState,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.intake_jobs import IntakeJobRepository
from reality_rag_persistence.repositories.stage_attempts import StageAttemptRepository
from reality_rag_persistence.repositories.stage_results import StageResultRepository
from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

from .domains.outbox import EventPublisher


class OrchestratorService:
    """Single-process orchestrator that records job/stage state.

    All writes to intake_jobs, stage_tasks, stage_attempts, stage_results
    must go through this service.
    """

    def __init__(self, session=None) -> None:
        if session is None:
            session = get_session()
            self._owns_session = True
        else:
            self._owns_session = False
        self._session = session
        self._intake_repo = IntakeJobRepository(session)
        self._task_repo = StageTaskRepository(session)
        self._attempt_repo = StageAttemptRepository(session)
        self._result_repo = StageResultRepository(session)
        self._event_publisher = EventPublisher(session)

    def create_intake_job(
        self,
        source_file_id: str,
        object_id: str,
        collection_id: str,
        trace_id: str = "",
    ) -> IntakeJob:
        """Create a new intake job in CREATED state."""
        intake_job_id = f"job-{uuid4().hex[:8]}"
        return self._intake_repo.create(
            intake_job_id=intake_job_id,
            source_file_id=source_file_id,
            object_id=object_id,
            collection_id=collection_id,
            trace_id=trace_id or intake_job_id,
        )

    def advance_state(
        self,
        intake_job_id: str,
        new_state: IntakeJobState,
        current_stage: str | None = None,
    ) -> bool:
        """Advance intake job state. Only orchestrator may call this."""
        return self._intake_repo.update_state(
            intake_job_id=intake_job_id,
            new_state=new_state,
            current_stage=current_stage,
        )

    def find_or_create_stage_task(
        self,
        intake_job_id: str,
        stage_name: StageName,
        idempotency_key: str,
        schema_version: str,
        input_hash: str,
    ) -> tuple[StageTask, bool]:
        """Find existing stage task or create a new one.

        Returns (stage_task, is_new).
        If a task with the same idempotency_key already exists,
        returns the existing task (is_new=False).
        """
        existing = self._task_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing, False

        stage_task_id = f"task-{uuid4().hex[:8]}"
        task = self._task_repo.create(
            stage_task_id=stage_task_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name.value,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            input_hash=input_hash,
        )
        # Phase 7: write StageTaskRequested outbox event atomically
        self._event_publisher.publish_stage_task_requested(
            intake_job_id=intake_job_id,
            stage_task_id=stage_task_id,
            stage_name=stage_name.value,
            input_hash=input_hash,
            idempotency_key=idempotency_key,
        )
        return task, True

    def check_existing_result(self, idempotency_key: str) -> StageResult | None:
        """Return existing stage result if the task already succeeded."""
        task = self._task_repo.find_succeeded_by_idempotency_key(idempotency_key)
        if task is None:
            return None
        return self._result_repo.get_by_stage_task(task.stage_task_id)

    def _ensure_aware(self, dt: datetime | None) -> datetime | None:
        """Ensure datetime has UTC tzinfo (SQLite may return naive)."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def acquire_lease(
        self,
        stage_task_id: str,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> bool:
        """Acquire a DB lease on a stage task.

        Returns True if the lease was acquired (task was unclaimed or
        previous lease expired). Returns False if another worker holds
        an active lease.
        """
        from datetime import timedelta

        task = self._task_repo.get(stage_task_id)
        if task is None:
            return False

        # Check if another worker holds an active lease
        if task.locked_by and task.locked_by != worker_id:
            lock_expires = self._ensure_aware(task.lock_expires_at)
            if lock_expires and lock_expires > datetime.now(timezone.utc):
                return False  # Lease still held by another worker

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        return self._task_repo.set_lock(stage_task_id, worker_id, expires_at)

    def release_lease(self, stage_task_id: str) -> bool:
        """Release the DB lease on a stage task."""
        return self._task_repo.clear_lock(stage_task_id)

    def start_stage_attempt(
        self,
        stage_task_id: str,
        intake_job_id: str,
        stage_name: StageName,
        worker_id: str = "",
    ) -> StageAttempt:
        """Start a new stage attempt under the given task."""
        self._task_repo.increment_attempt_count(stage_task_id)
        self._task_repo.update_state(stage_task_id, StageTaskState.RUNNING)

        # Determine attempt_no
        latest = self._attempt_repo.get_latest_by_stage_task(stage_task_id)
        attempt_no = (latest.attempt_no + 1) if latest is not None else 1

        stage_attempt_id = f"att-{uuid4().hex[:8]}"
        return self._attempt_repo.create(
            stage_attempt_id=stage_attempt_id,
            stage_task_id=stage_task_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name.value,
            attempt_no=attempt_no,
            worker_id=worker_id or None,
        )

    def complete_stage_attempt(
        self,
        stage_attempt_id: str,
        success: bool,
        error_code: str | None = None,
        error_summary_hash: str | None = None,
    ) -> bool:
        """Complete a stage attempt. Updates task state accordingly."""
        state = StageAttemptState.SUCCEEDED if success else StageAttemptState.FAILED
        return self._attempt_repo.complete(
            stage_attempt_id=stage_attempt_id,
            state=state,
            error_code=error_code,
            error_summary_hash=error_summary_hash,
        )

    def update_task_state(
        self,
        stage_task_id: str,
        state: StageTaskState,
    ) -> bool:
        """Update stage task state (e.g. after attempt completes)."""
        return self._task_repo.update_state(stage_task_id, state)

    def record_stage_result(
        self,
        stage_task_id: str,
        stage_attempt_id: str,
        intake_job_id: str,
        stage_name: StageName,
        idempotency_key: str,
        result_hash: str,
        result_ref: str | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> StageResult:
        """Record a successful stage result."""
        stage_result_id = f"res-{uuid4().hex[:8]}"
        return self._result_repo.create(
            stage_result_id=stage_result_id,
            stage_task_id=stage_task_id,
            stage_attempt_id=stage_attempt_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name.value,
            idempotency_key=idempotency_key,
            result_hash=result_hash,
            result_ref=result_ref,
            summary_json=summary_json,
        )

    def publish_stage_completed(
        self,
        *,
        intake_job_id: str,
        stage_task_id: str,
        stage_attempt_id: str,
        stage_name: StageName,
        success: bool,
        trace_id: str = "",
        **extra: Any,
    ) -> Any:
        """Write StageCompleted outbox event after stage persistence is finished."""
        return self._event_publisher.publish_stage_completed(
            intake_job_id=intake_job_id,
            stage_task_id=stage_task_id,
            stage_attempt_id=stage_attempt_id,
            stage_name=stage_name.value,
            success=success,
            trace_id=trace_id,
            **extra,
        )

    def fail_intake_job(self, intake_job_id: str, error_message: str) -> bool:
        """Mark intake job as failed and record error."""
        self._intake_repo.set_error(intake_job_id, error_message)
        return self._intake_repo.update_state(
            intake_job_id=intake_job_id,
            new_state=IntakeJobState.FAILED,
        )

    def set_preliminary_doc_id(
        self, intake_job_id: str, preliminary_doc_id: str
    ) -> bool:
        """Set preliminary_doc_id on the intake job."""
        return self._intake_repo.set_preliminary_doc_id(
            intake_job_id, preliminary_doc_id
        )

    def request_approval(
        self,
        intake_job_id: str,
        preliminary_doc_id: str,
        collection_id: str,
        **kwargs: Any,
    ) -> Any:
        """Write ApprovalRequested outbox event.

        The actual approval decision is made by approval-service consumer.
        """
        return self._event_publisher.publish_approval_requested(
            intake_job_id=intake_job_id,
            preliminary_doc_id=preliminary_doc_id,
            collection_id=collection_id,
            **kwargs,
        )

    def publish_completed(
        self,
        intake_job_id: str,
        final_doc_id: str,
        collection_id: str,
        **kwargs: Any,
    ) -> Any:
        """Write PublishCompleted outbox event."""
        return self._event_publisher.publish_publish_completed(
            intake_job_id=intake_job_id,
            final_doc_id=final_doc_id,
            collection_id=collection_id,
            **kwargs,
        )

    def close(self) -> None:
        """Close session if owned by this service."""
        if self._owns_session:
            self._session.close()
