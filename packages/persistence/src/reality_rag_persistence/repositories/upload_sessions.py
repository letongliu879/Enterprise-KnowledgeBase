"""Upload session repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import UploadSession, UploadSessionStatus

from ..models import UploadSessionModel


class UploadSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, upload_id: str) -> UploadSession | None:
        row = self._session.get(UploadSessionModel, upload_id)
        if row is None:
            return None
        return self._to_contract(row)

    def create(
        self,
        upload_id: str,
        source: str = "web",
        user_id: str | None = None,
        trace_id: str = "",
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> UploadSession:
        now = datetime.now(timezone.utc)
        row = UploadSessionModel(
            upload_id=upload_id,
            source=source,
            user_id=user_id,
            trace_id=trace_id,
            status=UploadSessionStatus.ACTIVE.value,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            received_size=0,
            created_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_status(
        self,
        upload_id: str,
        status: UploadSessionStatus,
        received_size: int | None = None,
    ) -> UploadSession | None:
        row = self._session.get(UploadSessionModel, upload_id)
        if row is None:
            return None
        row.status = status.value
        now = datetime.now(timezone.utc)
        row.updated_at = now
        if received_size is not None:
            row.received_size = received_size
            row.last_chunk_at = now
        if status == UploadSessionStatus.COMPLETED:
            row.completed_at = now
        self._session.flush()
        return self._to_contract(row)

    @staticmethod
    def _to_contract(row: UploadSessionModel) -> UploadSession:
        return UploadSession(
            upload_id=row.upload_id,
            source=row.source,
            user_id=row.user_id,
            trace_id=row.trace_id,
            status=row.status,
            expected_size=row.expected_size,
            expected_sha256=row.expected_sha256,
            received_size=row.received_size,
            created_at=row.created_at,
            last_chunk_at=row.last_chunk_at,
            completed_at=row.completed_at,
        )
