"""Source file repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import SourceFile, SourceFileState

from ..models import SourceFileModel


# Active states as defined in intake-pipeline.md
# Note: cleanable/cleaned/failed are NON-ACTIVE. A source file that has
# reached cleanable may be re-uploaded (e.g. user fixed content and
# re-submitted). Dedup for already-published docs is handled by the
# published_documents.source_content_hash index, not by active source file.
_ACTIVE_STATES = {
    "uploading",
    "uploaded",
    "scanning",
    "ready",
    "claimed",
    "consumed",
}


class SourceFileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, source_file_id: str) -> SourceFile | None:
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return None
        return self._to_contract(row)

    def find_active_by_content_hash(
        self, content_hash: str, collection_id: str
    ) -> SourceFile | None:
        """Return the active source file with matching content_hash in the same collection."""
        row = (
            self._session.query(SourceFileModel)
            .filter(SourceFileModel.content_hash == content_hash)
            .filter(SourceFileModel.collection_id == collection_id)
            .filter(SourceFileModel.state.in_(_ACTIVE_STATES))
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        source_file_id: str,
        collection_id: str,
        object_id: str,
        content_hash: str,
        *,
        upload_id: str | None = None,
        visibility: str = "INTERNAL",
        original_name: str = "",
        sanitized_name: str = "",
        size_bytes: int = 0,
        state: SourceFileState = SourceFileState.READY,
    ) -> SourceFile:
        now = datetime.now(timezone.utc)
        row = SourceFileModel(
            source_file_id=source_file_id,
            upload_id=upload_id,
            collection_id=collection_id,
            object_id=object_id,
            visibility=visibility,
            original_name=original_name,
            sanitized_name=sanitized_name,
            content_hash=content_hash,
            size_bytes=size_bytes,
            state=state.value,
            claimed_by_job_id=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self,
        source_file_id: str,
        state: SourceFileState,
        scan_result_id: str | None = None,
    ) -> SourceFile | None:
        """Update source file state. Returns updated source file or None."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return None
        row.state = state.value
        row.updated_at = datetime.now(timezone.utc)
        if scan_result_id is not None:
            row.scan_result_id = scan_result_id
        self._session.flush()
        return self._to_contract(row)

    def claim(self, source_file_id: str, job_id: str) -> bool:
        """Claim a source file for a job. Returns True if claim succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        if row.state != SourceFileState.READY.value or row.claimed_by_job_id is not None:
            return False
        row.state = SourceFileState.CLAIMED.value
        row.claimed_by_job_id = job_id
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        """Mark source file as consumed. Returns True if update succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        if row.state != SourceFileState.CLAIMED.value or row.claimed_by_job_id != job_id:
            return False
        row.state = SourceFileState.CONSUMED.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        """Mark source file as cleanable. Returns True if update succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        if row.claimed_by_job_id != job_id:
            return False
        if row.state not in (SourceFileState.CLAIMED.value, SourceFileState.CONSUMED.value):
            return False
        row.state = SourceFileState.CLEANABLE.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_cleaned(self, source_file_id: str) -> bool:
        """Mark source file as cleaned. Returns True if update succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        if row.state != SourceFileState.CLEANABLE.value:
            return False
        row.state = SourceFileState.CLEANED.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_failed(self, source_file_id: str) -> bool:
        """Mark source file as failed. Returns True if update succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        row.state = SourceFileState.FAILED.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def release_claim(self, source_file_id: str) -> bool:
        """Release claim back to READY. Returns True if update succeeded."""
        row = self._session.get(SourceFileModel, source_file_id)
        if row is None:
            return False
        if row.state != SourceFileState.CLAIMED.value:
            return False
        row.state = SourceFileState.READY.value
        row.claimed_by_job_id = None
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def list_by_object_id(self, object_id: str) -> list[SourceFile]:
        """Return all source files referencing the same object_id."""
        rows = (
            self._session.query(SourceFileModel)
            .filter(SourceFileModel.object_id == object_id)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def count_active_by_object_id(self, object_id: str) -> int:
        """Count how many source files still reference this object in active states."""
        from sqlalchemy import func
        return (
            self._session.query(func.count(SourceFileModel.source_file_id))
            .filter(SourceFileModel.object_id == object_id)
            .filter(SourceFileModel.state.in_(_ACTIVE_STATES))
            .scalar()
            or 0
        )

    @staticmethod
    def _to_contract(row: SourceFileModel) -> SourceFile:
        return SourceFile(
            source_file_id=row.source_file_id,
            upload_id=row.upload_id,
            object_id=row.object_id,
            collection_id=row.collection_id,
            visibility=row.visibility,
            original_name=row.original_name,
            sanitized_name=row.sanitized_name,
            content_hash=row.content_hash,
            size_bytes=row.size_bytes,
            state=SourceFileState(row.state),
            claimed_by_job_id=row.claimed_by_job_id,
            scan_result_id=row.scan_result_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            expires_at=row.expires_at,
        )
