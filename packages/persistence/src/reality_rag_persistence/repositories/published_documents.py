"""Published document repository. Owner: publishing domain."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import PublishedDocument, PublishedDocumentState

from ..models import PublishedDocumentModel


class PublishedDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, published_document_id: str) -> PublishedDocument | None:
        row = self._session.get(PublishedDocumentModel, published_document_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_final_doc_id(self, final_doc_id: str) -> PublishedDocument | None:
        row = (
            self._session.query(PublishedDocumentModel)
            .filter(PublishedDocumentModel.final_doc_id == final_doc_id)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_collection(self, collection_id: str) -> list[PublishedDocument]:
        rows = (
            self._session.query(PublishedDocumentModel)
            .filter(PublishedDocumentModel.collection_id == collection_id)
            .order_by(PublishedDocumentModel.created_at)
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        published_document_id: str,
        final_doc_id: str,
        logical_document_id: str,
        tenant_id: str,
        collection_id: str,
        version: int,
        source_content_hash: str = "",
        canonical_hash: str = "",
        state: PublishedDocumentState = PublishedDocumentState.PUBLISHED,
        active_index_version: str = "",
        created_by_ticket_id: str | None = None,
        asset_paths: dict | None = None,
    ) -> PublishedDocument:
        now = datetime.now(timezone.utc)
        row = PublishedDocumentModel(
            published_document_id=published_document_id,
            final_doc_id=final_doc_id,
            logical_document_id=logical_document_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            version=version,
            source_content_hash=source_content_hash,
            canonical_hash=canonical_hash,
            state=state.value,
            active_index_version=active_index_version,
            created_by_ticket_id=created_by_ticket_id,
            asset_paths=asset_paths or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self,
        published_document_id: str,
        new_state: PublishedDocumentState,
        previous_state: str | None = None,
    ) -> bool:
        row = self._session.get(PublishedDocumentModel, published_document_id)
        if row is None:
            return False
        row.previous_state = previous_state or row.state
        row.state = new_state.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def set_active_index_version(
        self, published_document_id: str, index_version: str
    ) -> bool:
        row = self._session.get(PublishedDocumentModel, published_document_id)
        if row is None:
            return False
        row.active_index_version = index_version
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: PublishedDocumentModel) -> PublishedDocument:
        return PublishedDocument(
            published_document_id=row.published_document_id,
            final_doc_id=row.final_doc_id,
            logical_document_id=row.logical_document_id,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            version=row.version,
            source_content_hash=row.source_content_hash,
            canonical_hash=row.canonical_hash,
            state=PublishedDocumentState(row.state),
            active_index_version=row.active_index_version,
            previous_state=row.previous_state,
            supersedes_final_doc_id=row.supersedes_final_doc_id,
            created_by_ticket_id=row.created_by_ticket_id,
            asset_paths=row.asset_paths or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
