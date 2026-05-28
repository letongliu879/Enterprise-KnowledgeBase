"""Collection profile binding repository."""

from sqlalchemy.orm import Session

from ..models import CollectionProfileBindingModel


class CollectionProfileBindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, binding_id: str) -> CollectionProfileBindingModel | None:
        return self._session.get(CollectionProfileBindingModel, binding_id)

    def list_by_collection(self, collection_id: str) -> list[CollectionProfileBindingModel]:
        return (
            self._session.query(CollectionProfileBindingModel)
            .filter(CollectionProfileBindingModel.collection_id == collection_id)
            .order_by(CollectionProfileBindingModel.binding_version.desc())
            .all()
        )

    def get_current_binding(self, collection_id: str) -> CollectionProfileBindingModel | None:
        return (
            self._session.query(CollectionProfileBindingModel)
            .filter(
                CollectionProfileBindingModel.collection_id == collection_id,
                CollectionProfileBindingModel.effective_to.is_(None),
            )
            .order_by(CollectionProfileBindingModel.binding_version.desc())
            .first()
        )

    def save(self, binding: CollectionProfileBindingModel) -> None:
        self._session.merge(binding)
        self._session.flush()

    def close_current_binding(self, collection_id: str) -> None:
        from datetime import datetime, timezone
        current = self.get_current_binding(collection_id)
        if current:
            current.effective_to = datetime.now(timezone.utc)
            self._session.merge(current)
            self._session.flush()
