"""Stage task DB lease service.

Worker must acquire a DB lease before executing a stage task.
Lease acquisition uses atomic UPDATE to guarantee only one worker wins.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import update

from reality_rag_contracts import StageTaskState
from reality_rag_persistence.models import StageTaskModel


class StageTaskLeaseService:
    """DB lease service for stage task execution.

    Rules:
      - Only one worker can hold the lease for a given stage_task_id.
      - Lease must be acquired via atomic UPDATE.
      - Worker must heartbeat to extend lease.
      - After lease expires, another worker can re-acquire.
      - Worker must verify it still holds the lease before committing results.
    """

    def __init__(self, session) -> None:
        self._session = session

    def acquire_lease(
        self,
        stage_task_id: str,
        worker_id: str,
        ttl_seconds: int = 600,
    ) -> bool:
        """Atomically acquire lease for a stage task.

        Returns True if lease was acquired, False otherwise.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        result = self._session.execute(
            update(StageTaskModel)
            .where(StageTaskModel.stage_task_id == stage_task_id)
            .where(StageTaskModel.state.in_([
                StageTaskState.QUEUED.value,
                StageTaskState.RETRY_SCHEDULED.value,
            ]))
            .where(
                (StageTaskModel.locked_by.is_(None))
                | (StageTaskModel.lock_expires_at < now)
            )
            .values(
                state=StageTaskState.RUNNING.value,
                locked_by=worker_id,
                lock_expires_at=expires_at,
                updated_at=now,
            )
        )
        self._session.flush()
        return result.rowcount == 1

    def heartbeat(
        self,
        stage_task_id: str,
        worker_id: str,
        ttl_seconds: int = 600,
    ) -> bool:
        """Extend lease if still held by this worker."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        result = self._session.execute(
            update(StageTaskModel)
            .where(StageTaskModel.stage_task_id == stage_task_id)
            .where(StageTaskModel.locked_by == worker_id)
            .values(
                lock_expires_at=expires_at,
                updated_at=now,
            )
        )
        self._session.flush()
        return result.rowcount == 1

    def release_lease(
        self,
        stage_task_id: str,
        worker_id: str,
        new_state: StageTaskState | None = None,
    ) -> bool:
        """Release lease held by this worker.

        Optionally update task state (e.g. back to QUEUED on failure).
        """
        now = datetime.now(timezone.utc)
        values = {
            "locked_by": None,
            "lock_expires_at": None,
            "updated_at": now,
        }
        if new_state is not None:
            values["state"] = new_state.value

        result = self._session.execute(
            update(StageTaskModel)
            .where(StageTaskModel.stage_task_id == stage_task_id)
            .where(StageTaskModel.locked_by == worker_id)
            .values(values)
        )
        self._session.flush()
        return result.rowcount == 1

    def verify_lease(self, stage_task_id: str, worker_id: str) -> bool:
        """Verify this worker still holds a non-expired lease."""
        from reality_rag_persistence.repositories.stage_tasks import StageTaskRepository

        task = StageTaskRepository(self._session).get(stage_task_id)
        if task is None:
            return False
        now = datetime.now(timezone.utc)
        expires_at = task.lock_expires_at
        if expires_at is None:
            return False
        # SQLite may return naive datetime; attach UTC if missing
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return task.locked_by == worker_id and expires_at > now
