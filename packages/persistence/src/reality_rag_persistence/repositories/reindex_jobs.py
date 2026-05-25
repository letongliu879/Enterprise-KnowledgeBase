"""Reindex job repository. Owner: publishing-worker."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import ReindexJob, ReindexJobState

from ..models import ReindexJobModel


class ReindexJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, reindex_job_id: str) -> ReindexJob | None:
        row = self._session.get(ReindexJobModel, reindex_job_id)
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        reindex_job_id: str,
        final_doc_id: str,
        collection_id: str,
        source_index_version: str,
        target_index_version: str,
    ) -> ReindexJob:
        now = datetime.now(timezone.utc)
        row = ReindexJobModel(
            reindex_job_id=reindex_job_id,
            final_doc_id=final_doc_id,
            collection_id=collection_id,
            source_index_version=source_index_version,
            target_index_version=target_index_version,
            state=ReindexJobState.CREATED.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(self, reindex_job_id: str, new_state: ReindexJobState) -> bool:
        row = self._session.get(ReindexJobModel, reindex_job_id)
        if row is None:
            return False
        row.state = new_state.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def complete(self, reindex_job_id: str, succeeded: bool, error_message: str | None = None) -> bool:
        row = self._session.get(ReindexJobModel, reindex_job_id)
        if row is None:
            return False
        row.state = ReindexJobState.SUCCEEDED.value if succeeded else ReindexJobState.FAILED.value
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
        row.updated_at = row.completed_at
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: ReindexJobModel) -> ReindexJob:
        return ReindexJob(
            reindex_job_id=row.reindex_job_id,
            final_doc_id=row.final_doc_id,
            collection_id=row.collection_id,
            source_index_version=row.source_index_version,
            target_index_version=row.target_index_version,
            state=ReindexJobState(row.state),
            index_build_job_id=row.index_build_job_id,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
            completed_at=row.completed_at,
        )
