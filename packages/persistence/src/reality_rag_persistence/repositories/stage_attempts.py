"""Stage attempt repository — orchestrator state owner."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import StageAttempt, StageAttemptState

from ..models import StageAttemptModel


class StageAttemptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, stage_attempt_id: str) -> StageAttempt | None:
        row = self._session.get(StageAttemptModel, stage_attempt_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_stage_task(self, stage_task_id: str) -> list[StageAttempt]:
        rows = (
            self._session.query(StageAttemptModel)
            .filter(StageAttemptModel.stage_task_id == stage_task_id)
            .order_by(StageAttemptModel.attempt_no)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def get_latest_by_stage_task(self, stage_task_id: str) -> StageAttempt | None:
        row = (
            self._session.query(StageAttemptModel)
            .filter(StageAttemptModel.stage_task_id == stage_task_id)
            .order_by(StageAttemptModel.attempt_no.desc())
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        stage_attempt_id: str,
        stage_task_id: str,
        intake_job_id: str,
        stage_name: str,
        attempt_no: int,
        worker_id: str | None = None,
    ) -> StageAttempt:
        now = datetime.now(timezone.utc)
        row = StageAttemptModel(
            stage_attempt_id=stage_attempt_id,
            stage_task_id=stage_task_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name,
            attempt_no=attempt_no,
            worker_id=worker_id,
            state=StageAttemptState.RUNNING.value,
            started_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def complete(
        self,
        stage_attempt_id: str,
        state: StageAttemptState,
        error_code: str | None = None,
        error_summary_hash: str | None = None,
    ) -> bool:
        row = self._session.get(StageAttemptModel, stage_attempt_id)
        if row is None:
            return False
        row.state = state.value
        if error_code is not None:
            row.error_code = error_code
        if error_summary_hash is not None:
            row.error_summary_hash = error_summary_hash
        row.finished_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: StageAttemptModel) -> StageAttempt:
        return StageAttempt(
            stage_attempt_id=row.stage_attempt_id,
            stage_task_id=row.stage_task_id,
            intake_job_id=row.intake_job_id,
            stage_name=row.stage_name,
            attempt_no=row.attempt_no,
            worker_id=row.worker_id,
            state=row.state,
            error_code=row.error_code,
            error_summary_hash=row.error_summary_hash,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
