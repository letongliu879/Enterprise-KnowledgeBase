"""Repository for workbench chunk edits."""

from sqlalchemy.orm import Session
from reality_rag_persistence.models import WorkbenchChunkEditModel


class ChunkEditRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, chunk_edit_id: str) -> WorkbenchChunkEditModel | None:
        return self._session.query(WorkbenchChunkEditModel).filter_by(chunk_edit_id=chunk_edit_id).first()

    def list_by_snapshot(self, parse_snapshot_id: str) -> list[WorkbenchChunkEditModel]:
        return self._session.query(WorkbenchChunkEditModel).filter_by(parse_snapshot_id=parse_snapshot_id).order_by(WorkbenchChunkEditModel.created_at.desc()).all()

    def list_by_source_file(self, source_file_id: str) -> list[WorkbenchChunkEditModel]:
        return self._session.query(WorkbenchChunkEditModel).filter_by(source_file_id=source_file_id).order_by(WorkbenchChunkEditModel.created_at.desc()).all()

    def save(self, model: WorkbenchChunkEditModel) -> None:
        self._session.merge(model)

    def submit(self, chunk_edit_id: str, downstream_revision_id: str) -> bool:
        """Atomically mark chunk edit as submitted (optimistic locking)."""
        from sqlalchemy import func as sa_func
        updated = (
            self._session.query(WorkbenchChunkEditModel)
            .filter_by(chunk_edit_id=chunk_edit_id, status="draft")
            .update({
                "status": "submitted",
                "downstream_revision_id": downstream_revision_id,
                "updated_at": sa_func.now(),
            })
        )
        return updated > 0

    def delete(self, chunk_edit_id: str) -> bool:
        model = self.get(chunk_edit_id)
        if model:
            self._session.delete(model)
            return True
        return False
