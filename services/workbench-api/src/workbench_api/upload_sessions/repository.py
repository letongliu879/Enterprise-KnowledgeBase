"""Repository for workbench upload sessions."""

from sqlalchemy.orm import Session
from reality_rag_persistence.models import WorkbenchUploadSessionModel


class UploadSessionRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, upload_id: str) -> WorkbenchUploadSessionModel | None:
        return self._session.query(WorkbenchUploadSessionModel).filter_by(upload_id=upload_id).first()

    def list_by_user(self, user_id: str, tenant_id: str | None = None, collection_id: str | None = None, status: str | None = None) -> list[WorkbenchUploadSessionModel]:
        query = self._session.query(WorkbenchUploadSessionModel).filter_by(user_id=user_id)
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        if collection_id:
            query = query.filter_by(collection_id=collection_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(WorkbenchUploadSessionModel.created_at.desc()).limit(10).all()

    def save(self, model: WorkbenchUploadSessionModel) -> None:
        self._session.merge(model)

    def delete(self, upload_id: str) -> bool:
        model = self.get(upload_id)
        if model:
            self._session.delete(model)
            return True
        return False

    def get_by_idempotency(self, user_id: str, collection_id: str, filename: str) -> WorkbenchUploadSessionModel | None:
        # Simple idempotency check: same user + collection + filename within a window could be duplicate
        # For strict idempotency, we use upload_id as the key
        return None
