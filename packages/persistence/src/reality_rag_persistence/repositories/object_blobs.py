"""Object blob repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import ObjectBlob, ObjectBlobStatus

from ..models import ObjectBlobModel


class ObjectBlobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, object_id: str) -> ObjectBlob | None:
        row = self._session.get(ObjectBlobModel, object_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_content_hash(self, content_hash: str) -> ObjectBlob | None:
        row = (
            self._session.query(ObjectBlobModel)
            .filter(ObjectBlobModel.content_hash == content_hash)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        object_id: str,
        content_hash: str,
        storage_key: str,
        size_bytes: int = 0,
    ) -> ObjectBlob:
        now = datetime.now(timezone.utc)
        row = ObjectBlobModel(
            object_id=object_id,
            content_hash=content_hash,
            storage_key=storage_key,
            size_bytes=size_bytes,
            ref_count=0,
            status=ObjectBlobStatus.ACTIVE.value,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def increment_ref(self, object_id: str) -> bool:
        """Increment ref_count. Returns True if object exists."""
        row = self._session.get(ObjectBlobModel, object_id)
        if row is None:
            return False
        row.ref_count += 1
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def decrement_ref(self, object_id: str) -> bool:
        """Decrement ref_count, never below 0. Returns True if object exists."""
        row = self._session.get(ObjectBlobModel, object_id)
        if row is None:
            return False
        row.ref_count = max(0, row.ref_count - 1)
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_gc_pending(self, object_id: str) -> bool:
        """Mark object as pending GC. Returns True if object exists."""
        row = self._session.get(ObjectBlobModel, object_id)
        if row is None:
            return False
        row.status = ObjectBlobStatus.GC_PENDING.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def mark_deleted(self, object_id: str) -> bool:
        """Mark object as deleted. Returns True if object exists."""
        row = self._session.get(ObjectBlobModel, object_id)
        if row is None:
            return False
        row.status = ObjectBlobStatus.DELETED.value
        row.deleted_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def list_gc_eligible(self) -> list[ObjectBlob]:
        """Return objects that are GC_PENDING or ACTIVE with ref_count == 0."""
        rows = (
            self._session.query(ObjectBlobModel)
            .filter(ObjectBlobModel.ref_count == 0)
            .filter(ObjectBlobModel.status != ObjectBlobStatus.DELETED.value)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    @staticmethod
    def _to_contract(row: ObjectBlobModel) -> ObjectBlob:
        return ObjectBlob(
            object_id=row.object_id,
            content_hash=row.content_hash,
            storage_key=row.storage_key,
            size_bytes=row.size_bytes,
            ref_count=row.ref_count,
            status=row.status,
            created_at=row.created_at,
            deleted_at=row.deleted_at,
        )
