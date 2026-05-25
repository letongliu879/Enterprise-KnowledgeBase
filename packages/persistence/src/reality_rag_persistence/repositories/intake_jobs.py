"""Intake job repository — orchestrator state owner."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import IntakeJob, IntakeJobState

from ..models import IntakeJobModel


class IntakeJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, intake_job_id: str) -> IntakeJob | None:
        row = self._session.get(IntakeJobModel, intake_job_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_source_file_id(self, source_file_id: str) -> IntakeJob | None:
        row = (
            self._session.query(IntakeJobModel)
            .filter(IntakeJobModel.source_file_id == source_file_id)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        intake_job_id: str,
        source_file_id: str,
        object_id: str,
        collection_id: str,
        trace_id: str = "",
        deadline_at: datetime | None = None,
    ) -> IntakeJob:
        now = datetime.now(timezone.utc)
        row = IntakeJobModel(
            intake_job_id=intake_job_id,
            source_file_id=source_file_id,
            object_id=object_id,
            collection_id=collection_id,
            state=IntakeJobState.CREATED.value,
            state_version=1,
            attempt_count=0,
            trace_id=trace_id or intake_job_id,
            created_at=now,
            updated_at=now,
            deadline_at=deadline_at,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self,
        intake_job_id: str,
        new_state: IntakeJobState,
        current_stage: str | None = None,
        state_version: int | None = None,
    ) -> bool:
        """Update state with optional optimistic locking.

        If state_version is provided, only updates when the current
        state_version matches (prevents lost updates).
        """
        row = self._session.get(IntakeJobModel, intake_job_id)
        if row is None:
            return False
        if state_version is not None and row.state_version != state_version:
            return False
        row.state = new_state.value
        if current_stage is not None:
            row.current_stage = current_stage
        row.state_version += 1
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def increment_attempt_count(self, intake_job_id: str) -> bool:
        row = self._session.get(IntakeJobModel, intake_job_id)
        if row is None:
            return False
        row.attempt_count += 1
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def set_preliminary_doc_id(self, intake_job_id: str, preliminary_doc_id: str) -> bool:
        row = self._session.get(IntakeJobModel, intake_job_id)
        if row is None:
            return False
        row.preliminary_doc_id = preliminary_doc_id
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def set_error(self, intake_job_id: str, error_message: str) -> bool:
        row = self._session.get(IntakeJobModel, intake_job_id)
        if row is None:
            return False
        row.error_message = error_message
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def list_by_collection(self, collection_id: str) -> list[IntakeJob]:
        rows = (
            self._session.query(IntakeJobModel)
            .filter(IntakeJobModel.collection_id == collection_id)
            .order_by(IntakeJobModel.created_at.asc())
            .all()
        )
        return [self._to_contract(r) for r in rows]

    @staticmethod
    def _to_contract(row: IntakeJobModel) -> IntakeJob:
        return IntakeJob(
            intake_job_id=row.intake_job_id,
            source_file_id=row.source_file_id,
            object_id=row.object_id,
            collection_id=row.collection_id,
            state=row.state,
            state_version=row.state_version,
            current_stage=row.current_stage,
            preliminary_doc_id=row.preliminary_doc_id,
            review_id=row.review_id,
            ticket_id=row.ticket_id,
            final_doc_id=row.final_doc_id,
            publish_id=row.publish_id,
            attempt_count=row.attempt_count,
            trace_id=row.trace_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deadline_at=row.deadline_at,
            error_message=row.error_message,
        )
