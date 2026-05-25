"""Indexed document repository. Owner: indexing-service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from reality_rag_contracts import IndexedDocument, IndexedDocumentState

from ..models import IndexedDocumentModel


class IndexedDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, indexed_document_id: str) -> IndexedDocument | None:
        row = self._session.get(IndexedDocumentModel, indexed_document_id)
        if row is None:
            return None
        return self._to_contract(row)

    def get_by_final_doc_and_version(
        self, final_doc_id: str, index_version: str
    ) -> IndexedDocument | None:
        row = (
            self._session.query(IndexedDocumentModel)
            .filter(
                IndexedDocumentModel.final_doc_id == final_doc_id,
                IndexedDocumentModel.index_version == index_version,
            )
            .first()
        )
        if row is None:
            return None
        return self._to_contract(row)

    def list_by_collection(
        self, collection_id: str, index_version: str | None = None
    ) -> list[IndexedDocument]:
        query = self._session.query(IndexedDocumentModel).filter(
            IndexedDocumentModel.collection_id == collection_id
        )
        if index_version is not None:
            query = query.filter(IndexedDocumentModel.index_version == index_version)
        rows = query.order_by(IndexedDocumentModel.created_at).all()
        return [self._to_contract(r) for r in rows]

    def list_all(self) -> list[IndexedDocument]:
        rows = self._session.query(IndexedDocumentModel).order_by(IndexedDocumentModel.created_at).all()
        return [self._to_contract(r) for r in rows]

    def create(
        self,
        indexed_document_id: str,
        final_doc_id: str,
        collection_id: str,
        index_version: str,
        parser_id: str = "",
        source_suffix: str = "",
        chunk_count: int = 0,
        embedding_count: int = 0,
        visible_chunk_count: int = 0,
        hidden_chunk_count: int = 0,
        has_toc_chunk: bool = False,
        has_parent_chunk: bool = False,
        document_metadata: dict | None = None,
        outline: list | None = None,
        state: IndexedDocumentState = IndexedDocumentState.CANDIDATE,
    ) -> IndexedDocument:
        now = datetime.now(timezone.utc)
        row = IndexedDocumentModel(
            indexed_document_id=indexed_document_id,
            final_doc_id=final_doc_id,
            collection_id=collection_id,
            index_version=index_version,
            parser_id=parser_id,
            source_suffix=source_suffix,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
            visible_chunk_count=visible_chunk_count,
            hidden_chunk_count=hidden_chunk_count,
            has_toc_chunk=has_toc_chunk,
            has_parent_chunk=has_parent_chunk,
            document_metadata=document_metadata or {},
            outline=outline or [],
            state=state.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_contract(row)

    def update_state(
        self, indexed_document_id: str, new_state: IndexedDocumentState
    ) -> bool:
        row = self._session.get(IndexedDocumentModel, indexed_document_id)
        if row is None:
            return False
        row.state = new_state.value
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    def activate(self, indexed_document_id: str) -> bool:
        row = self._session.get(IndexedDocumentModel, indexed_document_id)
        if row is None:
            return False
        row.state = IndexedDocumentState.ACTIVE.value
        row.activated_at = datetime.now(timezone.utc)
        row.updated_at = row.activated_at
        self._session.flush()
        return True

    def delete(self, indexed_document_id: str) -> bool:
        row = self._session.get(IndexedDocumentModel, indexed_document_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def update_counts(
        self,
        indexed_document_id: str,
        chunk_count: int,
        embedding_count: int,
        parser_id: str | None = None,
        source_suffix: str | None = None,
        visible_chunk_count: int | None = None,
        hidden_chunk_count: int | None = None,
        has_toc_chunk: bool | None = None,
        has_parent_chunk: bool | None = None,
        document_metadata: dict | None = None,
        outline: list | None = None,
    ) -> bool:
        row = self._session.get(IndexedDocumentModel, indexed_document_id)
        if row is None:
            return False
        row.chunk_count = chunk_count
        row.embedding_count = embedding_count
        if parser_id is not None:
            row.parser_id = parser_id
        if source_suffix is not None:
            row.source_suffix = source_suffix
        if visible_chunk_count is not None:
            row.visible_chunk_count = visible_chunk_count
        if hidden_chunk_count is not None:
            row.hidden_chunk_count = hidden_chunk_count
        if has_toc_chunk is not None:
            row.has_toc_chunk = has_toc_chunk
        if has_parent_chunk is not None:
            row.has_parent_chunk = has_parent_chunk
        if document_metadata is not None:
            row.document_metadata = document_metadata
        if outline is not None:
            row.outline = outline
        row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return True

    @staticmethod
    def _to_contract(row: IndexedDocumentModel) -> IndexedDocument:
        return IndexedDocument(
            indexed_document_id=row.indexed_document_id,
            final_doc_id=row.final_doc_id,
            collection_id=row.collection_id,
            index_version=row.index_version,
            parser_id=row.parser_id,
            source_suffix=row.source_suffix,
            chunk_count=row.chunk_count,
            embedding_count=row.embedding_count,
            visible_chunk_count=row.visible_chunk_count,
            hidden_chunk_count=row.hidden_chunk_count,
            has_toc_chunk=row.has_toc_chunk,
            has_parent_chunk=row.has_parent_chunk,
            document_metadata=row.document_metadata or {},
            outline=row.outline or [],
            state=IndexedDocumentState(row.state),
            activated_at=row.activated_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
