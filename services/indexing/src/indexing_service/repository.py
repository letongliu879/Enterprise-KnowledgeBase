from __future__ import annotations

import os
from asyncio import run
from hashlib import sha256

from indexing_service.asset_bundle import build_index_asset_bundle
from indexing_service.config import load_indexing_config
from indexing_service.backends import get_index_backend
from indexing_service.domain import (
    BuildJobRecord,
    ChunkRecordRecord,
    IndexBuildStatus,
    IndexVersionRecord,
    IndexVersionStatus,
    ParseSnapshotRecord,
)
from indexing_service._compat import utc_now
from indexing_service.projection_store import write_jsonl
from indexing_service.security import IndexingSecurity
from reality_rag_contracts import IndexedDocument, IndexedDocumentState


class InMemoryIndexingRepository:
    def __init__(self) -> None:
        self.DEFAULT_EMBEDDING_MODEL = load_indexing_config().models.embedding_model
        self.jobs_by_idempotency: dict[str, BuildJobRecord] = {}
        self.jobs_by_id: dict[str, BuildJobRecord] = {}
        self.index_versions: dict[str, IndexVersionRecord] = {}
        self.chunks_by_index_version: dict[str, list[ChunkRecordRecord]] = {}
        self.parse_snapshots_by_id: dict[str, ParseSnapshotRecord] = {}
        self.index_asset_bundles: dict[str, object] = {}
        self.indexed_documents_by_id: dict[str, IndexedDocument] = {}
        self.security = IndexingSecurity()
        self.index_backend = get_index_backend()

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
    ) -> BuildJobRecord:
        existing = self.jobs_by_idempotency.get(idempotency_key)
        if existing is not None:
            return existing
        job = BuildJobRecord(
            build_job_id=build_job_id,
            build_request_id=build_request_id,
            status=IndexBuildStatus.RUNNING,
            tenant_id=tenant_id,
            collection_id=collection_id,
            final_doc_id=final_doc_id,
            index_version_id=index_version_id,
            idempotency_key=idempotency_key,
        )
        self.jobs_by_idempotency[idempotency_key] = job
        self.jobs_by_id[build_job_id] = job
        self.index_versions.setdefault(
            index_version_id,
            IndexVersionRecord(
                index_version_id=index_version_id,
                tenant_id=tenant_id,
                collection_id=collection_id,
                status=IndexVersionStatus.BUILDING,
                schema_version="2026-05-23",
                index_profile_id=index_profile_id,
                chunk_profile_id="chunk_default",
                embedding_model=self.DEFAULT_EMBEDDING_MODEL,
                opensearch_index=f"os_{tenant_id}_{collection_id}_{index_version_id}",
                qdrant_collection=f"qd_{tenant_id}_{collection_id}_{index_version_id}",
            ),
        )
        self.jobs_by_id[build_job_id].status = IndexBuildStatus.RUNNING
        return job

    def get_job(self, build_job_id: str) -> BuildJobRecord:
        return self.jobs_by_id[build_job_id]

    def get_index_version(self, index_version_id: str) -> IndexVersionRecord:
        return self.index_versions[index_version_id]

    def activate(self, index_version_id: str) -> IndexVersionRecord:
        version = self.index_versions[index_version_id]
        previous_active = self._active_version_id(version.tenant_id, version.collection_id)
        if previous_active and previous_active != index_version_id:
            current = self.index_versions[previous_active]
            current.status = IndexVersionStatus.INACTIVE
            current.replaced_by_index_version_id = index_version_id
            for indexed_document in self.indexed_documents_by_id.values():
                if indexed_document.index_version == previous_active:
                    indexed_document.state = IndexedDocumentState.CANDIDATE
                    indexed_document.updated_at = utc_now()
        version.status = IndexVersionStatus.ACTIVE
        version.activated_at = utc_now()
        version.previous_active_index_version_id = previous_active if previous_active != index_version_id else version.previous_active_index_version_id
        version.replaced_by_index_version_id = None
        for indexed_document in self.indexed_documents_by_id.values():
            if indexed_document.index_version == index_version_id:
                indexed_document.state = IndexedDocumentState.ACTIVE
                indexed_document.activated_at = utc_now()
                indexed_document.updated_at = indexed_document.activated_at
        self._write_projections()
        return version

    def rollback(self, index_version_id: str) -> IndexVersionRecord:
        version = self.index_versions[index_version_id]
        version.status = IndexVersionStatus.ROLLED_BACK
        version.rolled_back_at = utc_now()
        for indexed_document in self.indexed_documents_by_id.values():
            if indexed_document.index_version == index_version_id:
                indexed_document.state = IndexedDocumentState.CANDIDATE
                indexed_document.updated_at = utc_now()
        fallback_index_version_id = version.previous_active_index_version_id
        if fallback_index_version_id and fallback_index_version_id in self.index_versions:
            fallback = self.index_versions[fallback_index_version_id]
            fallback.status = IndexVersionStatus.ACTIVE
            fallback.activated_at = utc_now()
            fallback.replaced_by_index_version_id = None
            for indexed_document in self.indexed_documents_by_id.values():
                if indexed_document.index_version == fallback_index_version_id:
                    indexed_document.state = IndexedDocumentState.ACTIVE
                    indexed_document.activated_at = utc_now()
                    indexed_document.updated_at = indexed_document.activated_at
        self._write_projections()
        return version

    def cleanup(self, index_version_id: str) -> tuple[IndexVersionRecord, int]:
        version = self.index_versions[index_version_id]
        if version.status == IndexVersionStatus.ACTIVE:
            raise ValueError("cannot cleanup an active index version")
        removed_chunks = len(self.chunks_by_index_version.get(index_version_id, []))
        self.chunks_by_index_version.pop(index_version_id, None)
        self.index_asset_bundles = {
            key: bundle
            for key, bundle in self.index_asset_bundles.items()
            if not str(key).startswith(f"{index_version_id}:")
        }
        self.indexed_documents_by_id = {
            key: value
            for key, value in self.indexed_documents_by_id.items()
            if value.index_version != index_version_id
        }
        version.chunk_count = 0
        version.status = IndexVersionStatus.DISCARDED
        version.cleaned_up_at = utc_now()
        self._write_projections()
        return version, removed_chunks

    def replace_chunks(self, index_version_id: str, chunks: list[ChunkRecordRecord]) -> None:
        existing = self.chunks_by_index_version.get(index_version_id, [])
        final_doc_ids = {chunk.final_doc_id for chunk in chunks}
        retained = [chunk for chunk in existing if chunk.final_doc_id not in final_doc_ids]
        self.chunks_by_index_version[index_version_id] = [*retained, *chunks]
        version = self.index_versions[index_version_id]
        version.chunk_count = len(self.chunks_by_index_version[index_version_id])
        if version.status != IndexVersionStatus.ACTIVE:
            version.status = IndexVersionStatus.READY
        self._write_projections()

    def write_index_assets(
        self,
        *,
        indexed_document_id: str,
        index_version_id: str,
        final_doc_id: str,
        canonical_source: str,
        chunks: list[ChunkRecordRecord],
    ) -> dict[str, int]:
        version = self.index_versions[index_version_id]
        bundle = build_index_asset_bundle(
            indexed_document_id=indexed_document_id,
            index_version=version,
            final_doc_id=final_doc_id,
            canonical_source=canonical_source,
            chunks=chunks,
        )
        self.index_asset_bundles[f"{index_version_id}:{final_doc_id}"] = bundle
        return run(self.index_backend.write_bundle(bundle))

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
        state: IndexedDocumentState = IndexedDocumentState.CANDIDATE,
    ) -> IndexedDocument:
        now = utc_now()
        existing = self.indexed_documents_by_id.get(indexed_document_id)
        record = IndexedDocument(
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
            document_metadata=dict(document_metadata or {}),
            outline=list(outline or []),
            state=state,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
            activated_at=(
                now
                if state == IndexedDocumentState.ACTIVE
                else (existing.activated_at if existing is not None else None)
            ),
        )
        self.indexed_documents_by_id[indexed_document_id] = record
        self._write_projections()
        return record

    def list_indexed_documents(self) -> list[IndexedDocument]:
        return list(self.indexed_documents_by_id.values())

    def list_chunks(self) -> list[ChunkRecordRecord]:
        return [chunk for chunks in self.chunks_by_index_version.values() for chunk in chunks]

    def list_active_chunks(self) -> list[ChunkRecordRecord]:
        active_versions = {
            version.index_version_id
            for version in self.index_versions.values()
            if version.status == IndexVersionStatus.ACTIVE
        }
        return [
            chunk
            for chunk in self.list_chunks()
            if chunk.index_version_id in active_versions
        ]

    def query_chunks(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        principal_groups: tuple[str, ...] = (),
        collection_id: str | None = None,
    ) -> list[ChunkRecordRecord]:
        visible: list[ChunkRecordRecord] = []
        for chunk in self.list_active_chunks():
            if chunk.tenant_id != tenant_id:
                continue
            if collection_id and chunk.collection_id != collection_id:
                continue
            if int(chunk.available_int) < 1:
                continue
            if self.security.can_access_chunk(
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_groups=principal_groups,
                chunk_access_control=chunk.access_control,
                chunk_visibility=chunk.visibility,
            ):
                visible.append(chunk)
        return visible

    def save_parse_snapshot(self, snapshot: ParseSnapshotRecord) -> ParseSnapshotRecord:
        self.parse_snapshots_by_id[snapshot.parse_snapshot_id] = snapshot
        self._write_parse_snapshots()
        return snapshot

    def get_parse_snapshot(self, parse_snapshot_id: str) -> ParseSnapshotRecord:
        return self.parse_snapshots_by_id[parse_snapshot_id]

    def _write_projections(self) -> None:
        write_jsonl(
            "REALITY_RAG_INDEX_VERSIONS_FILE",
            [version.model_dump(mode="json") for version in self.index_versions.values()],
        )
        write_jsonl(
            "REALITY_RAG_INDEXED_CHUNKS_FILE",
            [chunk.model_dump(mode="json") for chunk in self.list_chunks()],
        )
        write_jsonl(
            "REALITY_RAG_INDEXED_DOCUMENTS_FILE",
            [document.model_dump(mode="json") for document in self.list_indexed_documents()],
        )

    def _write_parse_snapshots(self) -> None:
        write_jsonl(
            "REALITY_RAG_PARSE_SNAPSHOTS_FILE",
            [snapshot.model_dump(mode="json") for snapshot in self.parse_snapshots_by_id.values()],
        )

    @staticmethod
    def stable_chunk_hash(content: str) -> str:
        return "sha256:" + sha256(content.encode("utf-8")).hexdigest()

    def mark_job_completed(self, build_job_id: str, *, failure_reason: str | None = None) -> BuildJobRecord:
        job = self.jobs_by_id[build_job_id]
        job.status = IndexBuildStatus.FAILED if failure_reason else IndexBuildStatus.READY
        job.failure_reason = failure_reason
        job.completed_at = utc_now()
        return job

    def _active_version_id(self, tenant_id: str, collection_id: str) -> str | None:
        for version in self.index_versions.values():
            if (
                version.tenant_id == tenant_id
                and version.collection_id == collection_id
                and version.status == IndexVersionStatus.ACTIVE
            ):
                return version.index_version_id
        return None


def create_indexing_repository():
    backend = os.environ.get("INDEXING_REGISTRY_BACKEND", "").strip().lower()
    if backend == "persistent":
        from indexing_service.persistent_repository import PersistentIndexingRepository

        return PersistentIndexingRepository()
    return InMemoryIndexingRepository()
