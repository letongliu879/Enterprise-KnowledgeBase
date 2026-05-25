"""Document repository."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import CanonicalMetadata

from ..models import DocumentModel


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, doc_id: str) -> CanonicalMetadata | None:
        row = self._session.get(DocumentModel, doc_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_logical_id(self, logical_document_id: str) -> CanonicalMetadata | None:
        row = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.logical_document_id == logical_document_id)
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_source_hash(self, source_hash: str, collection_id: str) -> CanonicalMetadata | None:
        """Return the active (non-archived) document with matching source_hash in the same collection."""
        row = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.source_hash == source_hash)
            .filter(DocumentModel.collection_id == collection_id)
            .filter(DocumentModel.archived.is_(False))
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_source_content_hash(
        self, content_hash: str, collection_id: str
    ) -> CanonicalMetadata | None:
        """Return the published non-archived document with matching source_content_hash."""
        row = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.source_content_hash == content_hash)
            .filter(DocumentModel.collection_id == collection_id)
            .filter(DocumentModel.archived.is_(False))
            .filter(DocumentModel.publish_status == "published")
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def get_latest_by_logical_id(self, logical_document_id: str, collection_id: str | None = None) -> CanonicalMetadata | None:
        """Return the latest non-archived version for a logical document."""
        query = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.logical_document_id == logical_document_id)
            .filter(DocumentModel.archived.is_(False))
        )
        if collection_id is not None:
            query = query.filter(DocumentModel.collection_id == collection_id)
        row = query.order_by(DocumentModel.version.desc()).first()
        if row is None:
            return None
        return self._to_contract(row)

    def archive_document(self, doc_id: str) -> None:
        """Soft-delete a document by setting archived=True."""
        row = self._session.get(DocumentModel, doc_id)
        if row is not None:
            row.archived = True
            row.updated_at = datetime.now(timezone.utc)
            self._session.flush()

    def list_all(self) -> list[CanonicalMetadata]:
        rows = self._session.query(DocumentModel).all()
        return [self._to_contract(r) for r in rows]

    def list_active(self) -> list[CanonicalMetadata]:
        """Return only non-archived documents (for retrieval and admin listings)."""
        rows = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.archived.is_(False))
            .all()
        )
        return [self._to_contract(r) for r in rows]

    def list_by_collection(
        self,
        collection_id: str,
        *,
        publish_status: str | None = None,
        index_status: str | None = None,
    ) -> list[CanonicalMetadata]:
        query = (
            self._session.query(DocumentModel)
            .filter(DocumentModel.collection_id == collection_id)
        )
        if publish_status is not None:
            query = query.filter(DocumentModel.publish_status == publish_status)
        if index_status is not None:
            query = query.filter(DocumentModel.index_status == index_status)
        rows = query.all()
        return [self._to_contract(r) for r in rows]

    def count(self) -> int:
        return self._session.query(DocumentModel).count()

    def count_by_collection(self) -> dict[str, int]:
        from sqlalchemy import func
        rows = (
            self._session.query(
                DocumentModel.collection_id,
                func.count(DocumentModel.doc_id),
            )
            .group_by(DocumentModel.collection_id)
            .all()
        )
        return {collection_id: count for collection_id, count in rows}

    def save(self, doc: CanonicalMetadata) -> None:
        row = DocumentModel(
            doc_id=doc.doc_id,
            logical_document_id=doc.logical_document_id,
            tenant_id=doc.tenant_id,
            collection_id=doc.collection_id,
            source_hash=doc.source_hash,
            source_content_hash=doc.source_content_hash or doc.source_hash,
            version=doc.version,
            archived=doc.archived,
            publish_status=doc.publish_status.value,
            index_status=doc.index_status.value,
            effective_date=doc.effective_date,
            authority_level=doc.authority_level,
            governance_level=doc.governance_level,
            access_policy=doc.access_policy,
            domain_tags=doc.domain_tags,
            risk_tags=doc.risk_tags,
            quality_summary=doc.quality_summary,
            processing_summary=doc.processing_summary,
            asset_paths=doc.asset_paths,
        )
        self._session.merge(row)
        self._session.flush()

    @staticmethod
    def _to_contract(row: DocumentModel) -> CanonicalMetadata:
        from reality_rag_contracts import PublishStatus, IndexStatus
        from datetime import datetime, timezone
        return CanonicalMetadata(
            doc_id=row.doc_id,
            logical_document_id=row.logical_document_id,
            tenant_id=row.tenant_id,
            collection_id=row.collection_id,
            source_hash=row.source_hash,
            source_content_hash=row.source_content_hash or row.source_hash or "",
            version=row.version,
            archived=row.archived or False,
            publish_status=PublishStatus(row.publish_status),
            index_status=IndexStatus(row.index_status),
            effective_date=row.effective_date,
            authority_level=row.authority_level or 0,
            governance_level=row.governance_level or "standard",
            access_policy=row.access_policy or "collection_default",
            domain_tags=row.domain_tags or [],
            risk_tags=row.risk_tags or [],
            quality_summary=row.quality_summary or "",
            processing_summary=row.processing_summary or "",
            asset_paths=row.asset_paths or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
