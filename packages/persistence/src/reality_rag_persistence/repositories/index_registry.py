"""Index Registry repository."""

from dataclasses import dataclass
from datetime import datetime

from reality_rag_contracts import IndexRegistryStatus
from sqlalchemy.orm import Session

from ..models import IndexRegistryModel


@dataclass
class IndexVersionEntry:
    collection_id: str
    index_version: str
    status: IndexRegistryStatus
    created_at: datetime | None = None
    previous_index_version: str | None = None
    target_index_version: str | None = None
    updated_at: datetime | None = None


class IndexRegistryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, collection_id: str) -> IndexVersionEntry | None:
        row = self._session.get(IndexRegistryModel, collection_id)
        if row is None:
            return None
        return IndexVersionEntry(
            collection_id=row.collection_id,
            index_version=row.index_version,
            status=IndexRegistryStatus(row.status),
            created_at=row.created_at,
            previous_index_version=row.previous_index_version,
            target_index_version=row.target_index_version,
            updated_at=row.updated_at,
        )

    def get_index_versions(
        self, collection_ids: list[str]
    ) -> dict[str, str]:
        """Return active versions for collections that are queryable.

        A collection remains queryable during indexing; retrieval should continue
        to use the currently active version until activation switches it.
        """
        queryable = {IndexRegistryStatus.INDEXED.value, IndexRegistryStatus.INDEXING.value}
        rows = (
            self._session.query(IndexRegistryModel)
            .filter(
                IndexRegistryModel.collection_id.in_(collection_ids),
                IndexRegistryModel.status.in_(queryable),
            )
            .all()
        )
        return {r.collection_id: r.index_version for r in rows if r.index_version}

    def list_all(self) -> list[IndexVersionEntry]:
        rows = self._session.query(IndexRegistryModel).all()
        return [
            IndexVersionEntry(
                collection_id=r.collection_id,
                index_version=r.index_version,
                status=IndexRegistryStatus(r.status),
                created_at=r.created_at,
                previous_index_version=r.previous_index_version,
                target_index_version=r.target_index_version,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def save(self, entry: IndexVersionEntry) -> None:
        row = IndexRegistryModel(
            collection_id=entry.collection_id,
            index_version=entry.index_version,
            previous_index_version=entry.previous_index_version,
            target_index_version=entry.target_index_version,
            status=entry.status.value,
            created_at=entry.created_at or datetime.now(),
            updated_at=entry.updated_at or datetime.now(),
        )
        self._session.merge(row)
        self._session.flush()

    def mark_indexing(self, collection_id: str, target_index_version: str) -> IndexVersionEntry:
        row = self._session.get(IndexRegistryModel, collection_id)
        now = datetime.now()
        if row is None:
            row = IndexRegistryModel(
                collection_id=collection_id,
                index_version=target_index_version,
                previous_index_version=None,
                target_index_version=target_index_version,
                status=IndexRegistryStatus.INDEXING.value,
                created_at=now,
                updated_at=now,
            )
        else:
            row.target_index_version = target_index_version
            row.status = IndexRegistryStatus.INDEXING.value
            row.updated_at = now
        self._session.merge(row)
        self._session.flush()
        return self.get(collection_id)

    def activate(self, collection_id: str, index_version: str | None = None) -> IndexVersionEntry:
        row = self._session.get(IndexRegistryModel, collection_id)
        if row is None:
            raise KeyError(collection_id)
        next_version = index_version or row.target_index_version or row.index_version
        row.previous_index_version = row.index_version
        row.index_version = next_version
        row.target_index_version = None
        row.status = IndexRegistryStatus.INDEXED.value
        row.updated_at = datetime.now()
        self._session.merge(row)
        self._session.flush()
        return self.get(collection_id)

    def rollback(self, collection_id: str, rollback_version: str | None = None) -> IndexVersionEntry:
        row = self._session.get(IndexRegistryModel, collection_id)
        if row is None:
            raise KeyError(collection_id)
        target = rollback_version or row.previous_index_version
        if not target:
            raise ValueError(f"No rollback target for collection {collection_id}")
        current = row.index_version
        row.index_version = target
        row.previous_index_version = current
        row.target_index_version = None
        row.status = IndexRegistryStatus.INDEXED.value
        row.updated_at = datetime.now()
        self._session.merge(row)
        self._session.flush()
        return self.get(collection_id)
