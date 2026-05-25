"""Publish job repository. Owner: publishing-worker."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import PublishJob, PublishJobState

from ..models import PublishJobModel


class PublishJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, publish_id: str) -> PublishJob | None:
        row = self._session.get(PublishJobModel, publish_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_collection(self, collection_id: str) -> list[PublishJob]:
        rows = (
            self._session.query(PublishJobModel)
            .filter(PublishJobModel.collection_id == collection_id)
            .order_by(PublishJobModel.created_at)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        publish_id: str,
        intake_job_id: str,
        final_doc_id: str,
        collection_id: str,
    ) -> PublishJob:
        now = datetime.now(timezone.utc)
        row = PublishJobModel(
            publish_id=publish_id,
            intake_job_id=intake_job_id,
            final_doc_id=final_doc_id,
            collection_id=collection_id,
            state=PublishJobState.CREATED.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self, publish_id: str, new_state: PublishJobState, stage: str = ""
    ) -> bool:
        row = self._session.get(PublishJobModel, publish_id)
        if row is None:
            return False
        row.state = new_state.value
        if stage:
            row.stage = stage
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def complete(self, publish_id: str, succeeded: bool, error_message: str | None = None) -> bool:
        row = self._session.get(PublishJobModel, publish_id)
        if row is None:
            return False
        row.state = PublishJobState.SUCCEEDED.value if succeeded else PublishJobState.FAILED.value
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
        row.updated_at = row.completed_at
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: PublishJobModel) -> PublishJob:
        return PublishJob(
            publish_id=row.publish_id,
            intake_job_id=row.intake_job_id,
            final_doc_id=row.final_doc_id,
            collection_id=row.collection_id,
            state=PublishJobState(row.state),
            stage=row.stage,
            asset_paths=row.asset_paths or {},
            index_build_job_id=row.index_build_job_id,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
            completed_at=row.completed_at,
        )
