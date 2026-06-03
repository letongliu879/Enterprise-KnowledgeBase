from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts.indexing_models import IndexVersionRecord, IndexVersionStatus

from ..models import IndexVersionModel


class IndexVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, index_version_id: str) -> IndexVersionRecord | None:
        row = self._session.get(IndexVersionModel, index_version_id)
        if row is None:
            return None
        return self._to_record(row)

    def list_all(self) -> list[IndexVersionRecord]:
        rows = self._session.query(IndexVersionModel).order_by(IndexVersionModel.created_at).all()
        return [self._to_record(row) for row in rows]

    def list_by_collection(self, collection_id: str) -> list[IndexVersionRecord]:
        rows = (
            self._session.query(IndexVersionModel)
            .filter(IndexVersionModel.collection_id == collection_id)
            .order_by(IndexVersionModel.created_at)
            .all()
        )
        return [self._to_record(row) for row in rows]

    def save(self, record: IndexVersionRecord) -> IndexVersionRecord:
        now = datetime.now(timezone.utc)
        row = IndexVersionModel(
            index_version_id=record.index_version_id,
            tenant_id=record.tenant_id,
            collection_id=record.collection_id,
            status=record.status.value,
            schema_version=record.schema_version,
            index_profile_id=record.index_profile_id,
            chunk_profile_id=record.chunk_profile_id,
            embedding_model=record.embedding_model,
            opensearch_index=record.opensearch_index,
            qdrant_collection=record.qdrant_collection,
            chunk_count=record.chunk_count,
            previous_active_index_version_id=record.previous_active_index_version_id,
            replaced_by_index_version_id=record.replaced_by_index_version_id,
            created_at=record.created_at,
            activated_at=record.activated_at,
            rolled_back_at=record.rolled_back_at,
            cleaned_up_at=record.cleaned_up_at,
            updated_at=now,
        )
        self._session.merge(row)
        self._session.flush()
        saved = self.get(record.index_version_id)
        assert saved is not None
        return saved

    def update_status(
        self,
        index_version_id: str,
        *,
        status: IndexVersionStatus,
        chunk_count: int | None = None,
        previous_active_index_version_id: str | None = None,
        replaced_by_index_version_id: str | None = None,
        activated_at: datetime | None = None,
        rolled_back_at: datetime | None = None,
        cleaned_up_at: datetime | None = None,
    ) -> IndexVersionRecord:
        row = self._session.get(IndexVersionModel, index_version_id)
        if row is None:
            raise KeyError(index_version_id)
        row.status = status.value
        if chunk_count is not None:
            row.chunk_count = chunk_count
        row.previous_active_index_version_id = previous_active_index_version_id
        row.replaced_by_index_version_id = replaced_by_index_version_id
        row.activated_at = activated_at
        row.rolled_back_at = rolled_back_at
        row.cleaned_up_at = cleaned_up_at
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        updated = self.get(index_version_id)
        assert updated is not None
        return updated

    @staticmethod
    def _to_record(row: IndexVersionModel) -> IndexVersionRecord:
        return IndexVersionRecord(
            index_version_id=row.index_version_id,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            status=IndexVersionStatus(row.status),
            schema_version=row.schema_version,
            index_profile_id=row.index_profile_id,
            chunk_profile_id=row.chunk_profile_id,
            embedding_model=row.embedding_model,
            opensearch_index=row.opensearch_index,
            qdrant_collection=row.qdrant_collection,
            chunk_count=row.chunk_count,
            previous_active_index_version_id=row.previous_active_index_version_id,
            replaced_by_index_version_id=row.replaced_by_index_version_id,
            created_at=row.created_at,
            activated_at=row.activated_at,
            rolled_back_at=row.rolled_back_at,
            cleaned_up_at=row.cleaned_up_at,
        )
