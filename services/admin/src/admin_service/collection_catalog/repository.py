"""Collection catalog repository wrapper."""

from sqlalchemy.orm import Session

from reality_rag_persistence.models import CollectionModel, CollectionProfileBindingModel
from reality_rag_persistence.repositories import CollectionRepository, CollectionProfileBindingRepository


class CollectionCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._collections = CollectionRepository(session)
        self._bindings = CollectionProfileBindingRepository(session)

    def get_collection(self, collection_id: str) -> CollectionModel | None:
        return self._session.get(CollectionModel, collection_id)

    def list_collections(self, tenant_id: str | None = None) -> list[CollectionModel]:
        query = self._session.query(CollectionModel)
        if tenant_id:
            query = query.filter(CollectionModel.tenant_id == tenant_id)
        return query.all()

    def save_collection(self, collection: CollectionModel) -> None:
        self._session.merge(collection)
        self._session.flush()

    def get_binding(self, binding_id: str) -> CollectionProfileBindingModel | None:
        return self._bindings.get(binding_id)

    def list_bindings(self, collection_id: str) -> list[CollectionProfileBindingModel]:
        return self._bindings.list_by_collection(collection_id)

    def get_current_binding(self, collection_id: str) -> CollectionProfileBindingModel | None:
        return self._bindings.get_current_binding(collection_id)

    def save_binding(self, binding: CollectionProfileBindingModel) -> None:
        self._bindings.save(binding)

    def close_current_binding(self, collection_id: str) -> None:
        self._bindings.close_current_binding(collection_id)
