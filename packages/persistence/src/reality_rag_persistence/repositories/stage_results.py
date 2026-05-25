"""Stage result repository — success-only persistence. Owner: intake-orchestrator."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from reality_rag_contracts import StageResult

from ..models import StageResultModel


class StageResultRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, stage_result_id: str) -> StageResult | None:
        row = self._session.get(StageResultModel, stage_result_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_stage_task(self, stage_task_id: str) -> StageResult | None:
        row = (
            self._session.query(StageResultModel)
            .filter(StageResultModel.stage_task_id == stage_task_id)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> StageResult | None:
        row = (
            self._session.query(StageResultModel)
            .filter(StageResultModel.idempotency_key == idempotency_key)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        stage_result_id: str,
        stage_task_id: str,
        stage_attempt_id: str,
        intake_job_id: str,
        stage_name: str,
        idempotency_key: str,
        result_hash: str,
        result_ref: str | None = None,
        summary_json: dict[str, Any] | None = None,
    ) -> StageResult:
        now = datetime.now(timezone.utc)
        row = StageResultModel(
            stage_result_id=stage_result_id,
            stage_task_id=stage_task_id,
            stage_attempt_id=stage_attempt_id,
            intake_job_id=intake_job_id,
            stage_name=stage_name,
            idempotency_key=idempotency_key,
            result_hash=result_hash,
            result_ref=result_ref,
            summary_json=summary_json or {},
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    @staticmethod
    def _to_contract(row: StageResultModel) -> StageResult:
        return StageResult(
            stage_result_id=row.stage_result_id,
            stage_task_id=row.stage_task_id,
            stage_attempt_id=row.stage_attempt_id,
            intake_job_id=row.intake_job_id,
            stage_name=row.stage_name,
            idempotency_key=row.idempotency_key,
            result_hash=row.result_hash,
            result_ref=row.result_ref,
            summary_json=row.summary_json or {},
            created_at=row.created_at,
        )
