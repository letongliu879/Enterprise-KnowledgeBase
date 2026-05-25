"""Index build job repository. Owner: indexing-service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import IndexBuildJob, IndexBuildJobState

from ..models import IndexBuildJobModel


class IndexBuildJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, index_build_job_id: str) -> IndexBuildJob | None:
        row = self._session.get(IndexBuildJobModel, index_build_job_id)
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_collection(self, collection_id: str) -> list[IndexBuildJob]:
        rows = (
            self._session.query(IndexBuildJobModel)
            .filter(IndexBuildJobModel.collection_id == collection_id)
            .order_by(IndexBuildJobModel.created_at)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        index_build_job_id: str,
        collection_id: str,
        target_index_version: str,
        publish_id: str | None = None,
        reindex_job_id: str | None = None,
    ) -> IndexBuildJob:
        now = datetime.now(timezone.utc)
        row = IndexBuildJobModel(
            index_build_job_id=index_build_job_id,
            collection_id=collection_id,
            target_index_version=target_index_version,
            publish_id=publish_id,
            reindex_job_id=reindex_job_id,
            state=IndexBuildJobState.CREATED.value,
            chunk_count=0,
            embedding_count=0,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self, index_build_job_id: str, new_state: IndexBuildJobState
    ) -> bool:
        row = self._session.get(IndexBuildJobModel, index_build_job_id)
        if row is None:
            return False
        row.state = new_state.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def update_progress(
        self,
        index_build_job_id: str,
        chunk_count: int,
        embedding_count: int,
    ) -> bool:
        row = self._session.get(IndexBuildJobModel, index_build_job_id)
        if row is None:
            return False
        row.chunk_count = chunk_count
        row.embedding_count = embedding_count
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def complete(
        self, index_build_job_id: str, succeeded: bool, error_message: str | None = None
    ) -> bool:
        row = self._session.get(IndexBuildJobModel, index_build_job_id)
        if row is None:
            return False
        row.state = (
            IndexBuildJobState.SUCCEEDED.value
            if succeeded
            else IndexBuildJobState.FAILED.value
        )
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
        row.updated_at = row.completed_at
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: IndexBuildJobModel) -> IndexBuildJob:
        return IndexBuildJob(
            index_build_job_id=row.index_build_job_id,
            collection_id=row.collection_id,
            target_index_version=row.target_index_version,
            publish_id=row.publish_id,
            reindex_job_id=row.reindex_job_id,
            state=IndexBuildJobState(row.state),
            chunk_count=row.chunk_count,
            embedding_count=row.embedding_count,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
            completed_at=row.completed_at,
        )
