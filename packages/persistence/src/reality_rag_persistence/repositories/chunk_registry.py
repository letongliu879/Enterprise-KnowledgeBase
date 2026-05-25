from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from indexing_service.domain import ChunkRecordRecord

from ..models import ChunkRegistryModel


class ChunkRegistryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_document_version(
        self,
        *,
        index_version_id: str,
        final_doc_id: str,
        chunks: list[ChunkRecordRecord],
    ) -> None:
        (
            self._session.query(ChunkRegistryModel)
            .filter(
                ChunkRegistryModel.index_version_id == index_version_id,
                ChunkRegistryModel.final_doc_id == final_doc_id,
            )
            .delete(synchronize_session=False)
        )
        now = datetime.now(timezone.utc)
        for chunk in chunks:
            self._session.add(
                ChunkRegistryModel(
                    chunk_id=chunk.chunk_id,
                    tenant_id=chunk.tenant_id,
                    collection_id=chunk.collection_id,
                    final_doc_id=chunk.final_doc_id,
                    index_version_id=chunk.index_version_id,
                    available_int=chunk.available_int,
                    visibility=chunk.visibility,
                    payload_json=chunk.model_dump(mode="json"),
                    created_at=now,
                    updated_at=now,
                )
            )
        self._session.flush()

    def list_by_index_version(self, index_version_id: str) -> list[ChunkRecordRecord]:
        rows = (
            self._session.query(ChunkRegistryModel)
            .filter(ChunkRegistryModel.index_version_id == index_version_id)
            .order_by(ChunkRegistryModel.created_at)
            .all()
        )
        return [ChunkRecordRecord.model_validate(row.payload_json or {}) for row in rows]

    def list_all(self) -> list[ChunkRecordRecord]:
        rows = self._session.query(ChunkRegistryModel).order_by(ChunkRegistryModel.created_at).all()
        return [ChunkRecordRecord.model_validate(row.payload_json or {}) for row in rows]

    def delete_by_index_version(self, index_version_id: str) -> int:
        deleted = (
            self._session.query(ChunkRegistryModel)
            .filter(ChunkRegistryModel.index_version_id == index_version_id)
            .delete(synchronize_session=False)
        )
        self._session.flush()
        return int(deleted or 0)
