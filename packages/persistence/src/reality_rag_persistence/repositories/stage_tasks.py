"""Stage task repository — orchestrator state owner."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import StageTask, StageTaskState

from ..models import StageTaskModel


class StageTaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, stage_task_id: str) -> StageTask | None:
        row = self._session.get(StageTaskModel, stage_task_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> StageTask | None:
        row = (
            self._session.query(StageTaskModel)
            .filter(StageTaskModel.idempotency_key == idempotency_key)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def find_succeeded_by_idempotency_key(self, idempotency_key: str) -> StageTask | None:
        """Return the stage task only if it has already succeeded."""
        row = (
            self._session.query(StageTaskModel)
            .filter(StageTaskModel.idempotency_key == idempotency_key)
            .filter(StageTaskModel.state == StageTaskState.SUCCEEDED.value)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_intake_job(self, intake_job_id: str) -> list[StageTask]:
        rows = (
            self._session.query(StageTaskModel)
            .filter(StageTaskModel.intake_job_id == intake_job_id)
            .order_by(StageTaskModel.created_at)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        stage_task_id: str,
        intake_job_id: str,
        stage_name: str,
        idempotency_key: str,
        schema_version: str,
        input_hash: str,
        next_run_at: datetime | None = None,
    ) -> StageTask:
        now = datetime.now(timezone.utc)
        row = StageTaskModel(
            stage_task_id=stage_task_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            input_hash=input_hash,
            state=StageTaskState.QUEUED.value,
            attempt_count=0,
            next_run_at=next_run_at or now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(self, stage_task_id: str, new_state: StageTaskState) -> bool:
        row = self._session.get(StageTaskModel, stage_task_id)
        if row is None:
            return False
        row.state = new_state.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def increment_attempt_count(self, stage_task_id: str) -> bool:
        row = self._session.get(StageTaskModel, stage_task_id)
        if row is None:
            return False
        row.attempt_count += 1
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def set_lock(
        self,
        stage_task_id: str,
        locked_by: str,
        lock_expires_at: datetime,
    ) -> bool:
        row = self._session.get(StageTaskModel, stage_task_id)
        if row is None:
            return False
        row.locked_by = locked_by
        row.lock_expires_at = lock_expires_at
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def find_stuck_running(self, stage_name: str) -> list[StageTask]:
        """Find stage tasks stuck in RUNNING with expired leases.

        These happen when a worker crashes after acquiring the lease but
        before completing the task.
        """
        now = datetime.now(timezone.utc)
        rows = (
            self._session.query(StageTaskModel)
            .filter(StageTaskModel.stage_name == stage_name)
            .filter(StageTaskModel.state == StageTaskState.RUNNING.value)
            .filter(StageTaskModel.lock_expires_at < now)
            .order_by(StageTaskModel.updated_at)
            .limit(10)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def clear_lock(self, stage_task_id: str) -> bool:
        row = self._session.get(StageTaskModel, stage_task_id)
        if row is None:
            return False
        row.locked_by = None
        row.lock_expires_at = None
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: StageTaskModel) -> StageTask:
        return StageTask(
            stage_task_id=row.stage_task_id,
            intake_job_id=row.intake_job_id,
            stage_name=row.stage_name,
            idempotency_key=row.idempotency_key,
            schema_version=row.schema_version,
            input_hash=row.input_hash,
            state=row.state,
            locked_by=row.locked_by,
            lock_expires_at=row.lock_expires_at,
            attempt_count=row.attempt_count,
            rerun_round=row.rerun_round,
            rerun_reason_code=row.rerun_reason_code,
            next_run_at=row.next_run_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
