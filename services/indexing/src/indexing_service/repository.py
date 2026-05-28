from __future__ import annotations

from typing import Protocol

from indexing_service.domain import (
    BuildJobRecord,
    ChunkRecord,
    IndexVersionRecord,
    ParseSnapshotRecord,
)
from reality_rag_contracts import IndexedDocument


class IndexingRepository(Protocol):
    def create_job(
        self,
        *,
        build_job_id: str,
        build_request_id: str,
        tenant_id: str,
        collection_id: str,
        final_doc_id: str,
        index_version_id: str,
        idempotency_key: str,
        index_profile_id: str,
        chunk_profile_id: str = "",
    ) -> BuildJobRecord: ...

    def get_job(self, build_job_id: str) -> BuildJobRecord: ...

    def get_index_version(self, index_version_id: str) -> IndexVersionRecord: ...

    def activate(self, index_version_id: str) -> IndexVersionRecord: ...

    def rollback(self, index_version_id: str) -> IndexVersionRecord: ...

    def cleanup(self, index_version_id: str) -> tuple[IndexVersionRecord, int]: ...

    def replace_chunks(self, index_version_id: str, chunks: list[ChunkRecord]) -> None: ...

    def write_index_assets(
        self,
        *,
        indexed_document_id: str,
        index_version_id: str,
        final_doc_id: str,
        canonical_source: str,
        chunks: list[ChunkRecord],
    ) -> dict[str, int]: ...

    def upsert_indexed_document(
        self,
        *,
        indexed_document_id: str,
        final_doc_id: str,
        collection_id: str,
        index_version: str,
        parser_id: str = "",
        source_suffix: str = "",
        chunk_count: int,
        embedding_count: int,
        visible_chunk_count: int = 0,
        hidden_chunk_count: int = 0,
        has_toc_chunk: bool = False,
        has_parent_chunk: bool = False,
        document_metadata: dict[str, object] | None = None,
        outline: list[dict[str, object]] | None = None,
        state=None,
    ) -> IndexedDocument: ...

    def list_indexed_documents(self) -> list[IndexedDocument]: ...

    def list_chunks(self) -> list[ChunkRecord]: ...

    def list_active_chunks(self) -> list[ChunkRecord]: ...

    def query_chunks(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        principal_groups: tuple[str, ...] = (),
        collection_id: str | None = None,
    ) -> list[ChunkRecord]: ...

    def save_parse_snapshot(self, snapshot: ParseSnapshotRecord) -> ParseSnapshotRecord: ...

    def get_parse_snapshot(self, parse_snapshot_id: str) -> ParseSnapshotRecord: ...

    def stable_chunk_hash(self, content: str) -> str: ...

    def list_chunk_revisions_by_doc(
        self,
        *,
        doc_id: str,
        collection_id: str,
        status: str | None = None,
    ) -> list[Any]: ...

    def mark_job_completed(
        self,
        build_job_id: str,
        *,
        error_message: str | None = None,
    ) -> BuildJobRecord: ...


def create_indexing_repository() -> IndexingRepository:
    from indexing_service.persistent_repository import PersistentIndexingRepository

    return PersistentIndexingRepository()
