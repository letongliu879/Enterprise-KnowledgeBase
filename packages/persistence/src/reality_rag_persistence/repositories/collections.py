"""Collection repository."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from reality_rag_contracts import Collection

from ..models import CollectionModel


class CollectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, collection_id: str) -> Collection | None:
        row = self._session.get(CollectionModel, collection_id)
        if row is None:
            return None
        return Collection(
            collection_id=row.collection_id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description or "",
            authority_level=row.authority_level or 0,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_all(self) -> list[Collection]:
        rows = self._session.query(CollectionModel).all()
        return [
            Collection(
                collection_id=r.collection_id,
                tenant_id=r.tenant_id,
                name=r.name,
                description=r.description or "",
                authority_level=r.authority_level or 0,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def list_by_tenant(self, tenant_id: str) -> list[Collection]:
        rows = (
            self._session.query(CollectionModel)
            .filter(CollectionModel.tenant_id == tenant_id)
            .all()
        )
        return [
            Collection(
                collection_id=r.collection_id,
                tenant_id=r.tenant_id,
                name=r.name,
                description=r.description or "",
                authority_level=r.authority_level or 0,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def save(self, collection: Collection) -> None:
        row = CollectionModel(
            collection_id=collection.collection_id,
            tenant_id=collection.tenant_id,
            name=collection.name,
            description=collection.description,
            authority_level=collection.authority_level,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )
        self._session.execute(
            pg_insert(CollectionModel)
            .values(
                collection_id=row.collection_id,
                tenant_id=row.tenant_id,
                name=row.name,
                description=row.description,
                authority_level=row.authority_level,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            .on_conflict_do_update(
                index_elements=["collection_id"],
                set_={
                    "tenant_id": row.tenant_id,
                    "name": row.name,
                    "description": row.description,
                    "authority_level": row.authority_level,
                    "updated_at": row.updated_at,
                },
            )
        )
        self._session.flush()

    def count(self) -> int:
        return self._session.query(CollectionModel).count()
