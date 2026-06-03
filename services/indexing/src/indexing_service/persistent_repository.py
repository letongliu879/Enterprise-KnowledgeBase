from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from indexing_service._compat import utc_now
from indexing_service.asset_bundle import build_index_asset_bundle
from indexing_service.backends import get_index_backend
from indexing_service.config import load_indexing_config
from indexing_service.domain import (
    BuildJobRecord,
    ChunkRevisionRecord,
    IndexBuildStatus,
)
from reality_rag_contracts.indexing_models import (
    ChunkRecord,
    IndexVersionRecord,
    IndexVersionStatus,
    ParseSnapshotRecord,
)
from indexing_service.security import IndexingSecurity
from reality_rag_contracts import IndexedDocument, IndexedDocumentState
from reality_rag_persistence.database import create_all, get_session
from reality_rag_persistence.repositories import (
    ChunkRegistryRepository,
    IndexBuildJobRepository,
    IndexedDocumentRepository,
    IndexRegistryRepository,
    IndexVersionRepository,
    ParseSnapshotRepository,
)


@dataclass
class _PersistentState:
    build_job_repo: IndexBuildJobRepository
    chunk_registry_repo: ChunkRegistryRepository
    indexed_document_repo: IndexedDocumentRepository
    index_registry_repo: IndexRegistryRepository
    index_version_repo: IndexVersionRepository
    parse_snapshot_repo: ParseSnapshotRepository


class PersistentIndexingRepository:
    def __init__(self) -> None:
        create_all()
        self.DEFAULT_EMBEDDING_MODEL = load_indexing_config().models.embedding_model
        self.jobs_by_idempotency: dict[str, BuildJobRecord] = {}
        self.jobs_by_id: dict[str, BuildJobRecord] = {}
        self.index_versions: dict[str, IndexVersionRecord] = {}
        self.chunks_by_index_version: dict[str, list[ChunkRecord]] = {}
        self.parse_snapshots_by_id: dict[str, ParseSnapshotRecord] = {}
        self.index_asset_bundles: dict[str, object] = {}
        self.indexed_documents_by_id: dict[str, IndexedDocument] = {}
        self.chunk_revisions_by_id: dict[str, ChunkRevisionRecord] = {}
        self.chunk_revision_idempotency: dict[str, ChunkRevisionRecord] = {}
        self.security = IndexingSecurity()
        self.index_backend = get_index_backend()
        self._hydrate_from_db()

    def _db(self) -> tuple[object, _PersistentState]:
        session = get_session()
        return session, _PersistentState(
            build_job_repo=IndexBuildJobRepository(session),
            chunk_registry_repo=ChunkRegistryRepository(session),
            indexed_document_repo=IndexedDocumentRepository(session),
            index_registry_repo=IndexRegistryRepository(session),
            index_version_repo=IndexVersionRepository(session),
            parse_snapshot_repo=ParseSnapshotRepository(session),
        )

    def _hydrate_from_db(self) -> None:
        session, repos = self._db()
        try:
            registry_entries = repos.index_registry_repo.list_all()
            for index_version in repos.index_version_repo.list_all():
                self.index_versions[index_version.index_version_id] = index_version
            indexed_documents = repos.indexed_document_repo.list_all()
            for indexed_document in indexed_documents:
                self.indexed_documents_by_id[indexed_document.indexed_document_id] = indexed_document
            chunks = repos.chunk_registry_repo.list_all()
            for chunk in chunks:
                self.chunks_by_index_version.setdefault(chunk.index_version_id, []).append(chunk)
            synthesized = _synthesize_missing_index_versions(
                existing=self.index_versions,
                registry_entries=registry_entries,
                indexed_documents=indexed_documents,
                chunks=chunks,
                embedding_model=self.DEFAULT_EMBEDDING_MODEL,
            )
            for record in synthesized:
                repos.index_version_repo.save(record)
                self.index_versions[record.index_version_id] = record
            if synthesized:
                session.commit()
        finally:
            session.close()

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
        version_record = self.index_versions.get(index_version_id) or IndexVersionRecord(
            index_version_id=index_version_id,
            tenant_id=tenant_id,
            collection_id=collection_id,
            status=IndexVersionStatus.BUILDING,
            schema_version="2026-05-26",
            index_profile_id=index_profile_id,
            chunk_profile_id=chunk_profile_id or "chunk_default",
            embedding_model=self.DEFAULT_EMBEDDING_MODEL,
            opensearch_index=f"os_{tenant_id}_{collection_id}_{index_version_id}",
            qdrant_collection=f"qd_{tenant_id}_{collection_id}_{index_version_id}",
        )
        session, repos = self._db()
        try:
            repos.build_job_repo.create(
                index_build_job_id=build_job_id,
                collection_id=collection_id,
                target_index_version=index_version_id,
            )
            repos.build_job_repo.update_state(build_job_id, _to_contract_job_state(IndexBuildStatus.RUNNING))
            repos.index_registry_repo.mark_indexing(collection_id, index_version_id)
            repos.index_version_repo.save(version_record)
            session.commit()
        finally:
            session.close()
        # DB transaction succeeded: refresh in-memory projection
        self.jobs_by_idempotency[idempotency_key] = job
        self.jobs_by_id[build_job_id] = job
        self.index_versions[index_version_id] = version_record
        return job

    def get_job(self, build_job_id: str) -> BuildJobRecord:
        job = self.jobs_by_id.get(build_job_id)
        if job is not None:
            return job
        raise KeyError(build_job_id)

    def get_index_version(self, index_version_id: str) -> IndexVersionRecord:
        session, repos = self._db()
        try:
            persisted = repos.index_version_repo.get(index_version_id)
        finally:
            session.close()
        if persisted is not None:
            self.index_versions[index_version_id] = persisted
            return persisted
        return self.index_versions[index_version_id]

    def activate(self, index_version_id: str) -> IndexVersionRecord:
        version = self.get_index_version(index_version_id)
        previous_active = self._active_version_id(version.collection_id)
        activated_at = utc_now()

        # Prepare new records for DB without mutating in-memory state yet
        new_version = version.model_copy(update={
            "status": IndexVersionStatus.ACTIVE,
            "activated_at": activated_at,
            "previous_active_index_version_id": (
                previous_active if previous_active != index_version_id else version.previous_active_index_version_id
            ),
            "replaced_by_index_version_id": None,
        })
        new_current = None
        if previous_active and previous_active != index_version_id:
            current = self.get_index_version(previous_active)
            new_current = current.model_copy(update={
                "status": IndexVersionStatus.INACTIVE,
                "replaced_by_index_version_id": index_version_id,
            })

        session, repos = self._db()
        try:
            repos.index_registry_repo.activate(version.collection_id, index_version_id)
            repos.index_version_repo.save(new_version)
            if new_current is not None:
                repos.index_version_repo.save(new_current)
            for indexed_document in self.indexed_documents_by_id.values():
                if indexed_document.collection_id != version.collection_id:
                    continue
                if indexed_document.index_version == index_version_id:
                    repos.indexed_document_repo.activate(indexed_document.indexed_document_id)
                else:
                    repos.indexed_document_repo.update_state(
                        indexed_document.indexed_document_id,
                        IndexedDocumentState.CANDIDATE,
                    )
            session.commit()
        finally:
            session.close()

        # DB committed successfully: refresh in-memory projection
        self.index_versions[index_version_id] = new_version
        if new_current is not None:
            self.index_versions[previous_active] = new_current
        for indexed_document in self.indexed_documents_by_id.values():
            if indexed_document.collection_id != version.collection_id:
                continue
            if indexed_document.index_version == index_version_id:
                indexed_document.state = IndexedDocumentState.ACTIVE
                indexed_document.activated_at = activated_at
                indexed_document.updated_at = activated_at
            else:
                indexed_document.state = IndexedDocumentState.CANDIDATE
                indexed_document.updated_at = activated_at
        return new_version

    def rollback(self, index_version_id: str) -> IndexVersionRecord:
        version = self.get_index_version(index_version_id)
        rolled_back_at = utc_now()
        fallback_index_version_id = version.previous_active_index_version_id

        # Prepare new records for DB without mutating in-memory state yet
        new_version = version.model_copy(update={
            "status": IndexVersionStatus.ROLLED_BACK,
            "rolled_back_at": rolled_back_at,
        })
        new_fallback = None
        if fallback_index_version_id and fallback_index_version_id in self.index_versions:
            fallback = self.get_index_version(fallback_index_version_id)
            new_fallback = fallback.model_copy(update={
                "status": IndexVersionStatus.ACTIVE,
                "activated_at": rolled_back_at,
                "replaced_by_index_version_id": None,
            })

        session, repos = self._db()
        try:
            repos.index_registry_repo.rollback(version.collection_id, fallback_index_version_id)
            repos.index_version_repo.save(new_version)
            if new_fallback is not None:
                repos.index_version_repo.save(new_fallback)
            if new_fallback is not None:
                for indexed_document in self.indexed_documents_by_id.values():
                    if indexed_document.collection_id != version.collection_id:
                        continue
                    if indexed_document.index_version == fallback_index_version_id:
                        repos.indexed_document_repo.activate(indexed_document.indexed_document_id)
                    else:
                        repos.indexed_document_repo.update_state(
                            indexed_document.indexed_document_id,
                            IndexedDocumentState.CANDIDATE,
                        )
            for indexed_document in self.indexed_documents_by_id.values():
                if indexed_document.collection_id != version.collection_id:
                    continue
                if indexed_document.index_version == index_version_id:
                    repos.indexed_document_repo.update_state(
                        indexed_document.indexed_document_id,
                        IndexedDocumentState.CANDIDATE,
                    )
            session.commit()
        finally:
            session.close()

        # DB committed successfully: refresh in-memory projection
        self.index_versions[index_version_id] = new_version
        if new_fallback is not None:
            self.index_versions[fallback_index_version_id] = new_fallback
        for indexed_document in self.indexed_documents_by_id.values():
            if indexed_document.collection_id != version.collection_id:
                continue
            if indexed_document.index_version == fallback_index_version_id:
                indexed_document.state = IndexedDocumentState.ACTIVE
                indexed_document.activated_at = rolled_back_at
                indexed_document.updated_at = rolled_back_at
            elif indexed_document.index_version == index_version_id:
                indexed_document.state = IndexedDocumentState.CANDIDATE
                indexed_document.updated_at = rolled_back_at
            else:
                indexed_document.state = IndexedDocumentState.CANDIDATE
                indexed_document.updated_at = rolled_back_at
        return new_version

    def cleanup(self, index_version_id: str) -> tuple[IndexVersionRecord, int]:
        version = self.get_index_version(index_version_id)
        if version.status == IndexVersionStatus.ACTIVE:
            raise ValueError("cannot cleanup an active index version")
        removed_chunks = len(self.chunks_by_index_version.get(index_version_id, []))
        remove_ids = [
            key
            for key, value in self.indexed_documents_by_id.items()
            if value.index_version == index_version_id
        ]
        new_version = version.model_copy(update={
            "chunk_count": 0,
            "status": IndexVersionStatus.DISCARDED,
            "cleaned_up_at": utc_now(),
        })
        session, repos = self._db()
        try:
            repos.chunk_registry_repo.delete_by_index_version(index_version_id)
            for indexed_document_id in remove_ids:
                repos.indexed_document_repo.delete(indexed_document_id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        session, repos = self._db()
        try:
            repos.index_version_repo.save(new_version)
            session.commit()
        finally:
            session.close()
        # Both transactions committed: refresh in-memory projection
        self.chunks_by_index_version.pop(index_version_id, None)
        self.index_asset_bundles = {
            key: bundle
            for key, bundle in self.index_asset_bundles.items()
            if not str(key).startswith(f"{index_version_id}:")
        }
        for key in remove_ids:
            self.indexed_documents_by_id.pop(key, None)
        self.index_versions[index_version_id] = new_version
        return new_version, removed_chunks

    def replace_chunks(self, index_version_id: str, chunks: list[ChunkRecord]) -> None:
        existing = self.chunks_by_index_version.get(index_version_id, [])
        final_doc_ids = {chunk.final_doc_id for chunk in chunks}
        retained = [chunk for chunk in existing if chunk.final_doc_id not in final_doc_ids]
        merged_chunks = [*retained, *chunks]
        version = self.index_versions[index_version_id]
        new_version = version.model_copy(update={
            "chunk_count": len(merged_chunks),
            "status": IndexVersionStatus.READY if version.status != IndexVersionStatus.ACTIVE else version.status,
        })
        session, repos = self._db()
        try:
            for final_doc_id in final_doc_ids:
                doc_chunks = [chunk for chunk in chunks if chunk.final_doc_id == final_doc_id]
                repos.chunk_registry_repo.replace_for_document_version(
                    index_version_id=index_version_id,
                    final_doc_id=final_doc_id,
                    chunks=doc_chunks,
                )
            repos.index_version_repo.save(new_version)
            session.commit()
        finally:
            session.close()
        # DB committed successfully: refresh in-memory projection
        self.chunks_by_index_version[index_version_id] = merged_chunks
        self.index_versions[index_version_id] = new_version
    def write_index_assets(
        self,
        *,
        indexed_document_id: str,
        index_version_id: str,
        final_doc_id: str,
        canonical_source: str,
        chunks: list[ChunkRecord],
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
        return __import__("asyncio").run(self.index_backend.write_bundle(bundle))

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
        existing = self.indexed_documents_by_id.get(indexed_document_id)
        session, repos = self._db()
        try:
            if existing is None:
                record = repos.indexed_document_repo.create(
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
                )
            else:
                repos.indexed_document_repo.update_counts(
                    indexed_document_id=indexed_document_id,
                    chunk_count=chunk_count,
                    embedding_count=embedding_count,
                    parser_id=parser_id,
                    source_suffix=source_suffix,
                    visible_chunk_count=visible_chunk_count,
                    hidden_chunk_count=hidden_chunk_count,
                    has_toc_chunk=has_toc_chunk,
                    has_parent_chunk=has_parent_chunk,
                    document_metadata=dict(document_metadata or {}),
                    outline=list(outline or []),
                )
                if state == IndexedDocumentState.ACTIVE:
                    repos.indexed_document_repo.activate(indexed_document_id)
                else:
                    repos.indexed_document_repo.update_state(indexed_document_id, state)
                record = repos.indexed_document_repo.get(indexed_document_id)
            session.commit()
        finally:
            session.close()
        self.indexed_documents_by_id[indexed_document_id] = record
        return record

    def list_indexed_documents(self) -> list[IndexedDocument]:
        return [doc for doc in self.indexed_documents_by_id.values() if doc is not None]

    def list_chunks(self) -> list[ChunkRecord]:
        return [chunk for chunks in self.chunks_by_index_version.values() for chunk in chunks]

    def list_active_chunks(self) -> list[ChunkRecord]:
        session, repos = self._db()
        try:
            registry_entries = repos.index_registry_repo.list_all()
        finally:
            session.close()
        active_versions = {entry.index_version for entry in registry_entries if entry.index_version}
        return [chunk for chunk in self.list_chunks() if chunk.index_version_id in active_versions]

    def query_chunks(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        principal_groups: tuple[str, ...] = (),
        collection_id: str | None = None,
    ) -> list[ChunkRecord]:
        visible: list[ChunkRecord] = []
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

    def create_chunk_revision(
        self,
        *,
        revision_id: str,
        base_evidence_id: str,
        doc_id: str,
        collection_id: str,
        tenant_id: str,
        operation: str = "update",
        content: str | None = None,
        vector_text: str | None = None,
        section_path: list[str] | None = None,
        metadata_patch: dict[str, object] | None = None,
        citation_payload: dict[str, object] | None = None,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> ChunkRevisionRecord:
        if idempotency_key and idempotency_key in self.chunk_revision_idempotency:
            return self.chunk_revision_idempotency[idempotency_key]

        # Find base chunk
        base_chunk = None
        for chunk in self.list_chunks():
            if chunk.chunk_id == base_evidence_id:
                base_chunk = chunk
                break

        if base_chunk is None:
            raise KeyError(f"Base chunk not found: {base_evidence_id}")

        # Validate tenant/collection match
        if base_chunk.tenant_id != tenant_id or base_chunk.collection_id != collection_id:
            raise ValueError("Tenant or collection mismatch with base chunk")

        revision = ChunkRevisionRecord(
            revision_id=revision_id,
            base_evidence_id=base_evidence_id,
            doc_id=doc_id,
            collection_id=collection_id,
            tenant_id=tenant_id,
            operation=operation,
            content=content,
            vector_text=vector_text,
            section_path=section_path,
            metadata_patch=metadata_patch,
            citation_payload=citation_payload,
            status="draft",
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )
        self.chunk_revisions_by_id[revision_id] = revision
        if idempotency_key:
            self.chunk_revision_idempotency[idempotency_key] = revision
        return revision

    def get_chunk_revision(self, revision_id: str) -> ChunkRevisionRecord:
        revision = self.chunk_revisions_by_id.get(revision_id)
        if revision is not None:
            return revision
        raise KeyError(revision_id)

    def list_chunk_revisions_by_doc(
        self,
        *,
        doc_id: str,
        collection_id: str,
        status: str | None = None,
    ) -> list[ChunkRevisionRecord]:
        """Return chunk revisions for a document, optionally filtered by status."""
        results: list[ChunkRevisionRecord] = []
        for revision in self.chunk_revisions_by_id.values():
            if revision.doc_id != doc_id or revision.collection_id != collection_id:
                continue
            if status is not None and revision.status != status:
                continue
            results.append(revision)
        return results

    def materialize_chunk_revision(self, revision_id: str) -> dict[str, object]:
        revision = self.get_chunk_revision(revision_id)
        if revision.status not in ("draft", "failed"):
            return {
                "revision_id": revision_id,
                "status": revision.status,
                "message": "Revision already materialized or in progress",
            }

        revision.status = "materializing"
        revision.updated_at = utc_now()

        try:
            # Find base chunk
            base_chunk = None
            for chunk in self.list_chunks():
                if chunk.chunk_id == revision.base_evidence_id:
                    base_chunk = chunk
                    break

            if base_chunk is None:
                revision.status = "failed"
                revision.updated_at = utc_now()
                raise ValueError(f"Base chunk not found during materialization: {revision.base_evidence_id}")

            # Apply operation to create new chunk
            new_chunk = self._apply_chunk_revision(base_chunk, revision)

            # Write to index backend
            version = self.index_versions.get(new_chunk.index_version_id)
            if version is None:
                revision.status = "failed"
                revision.updated_at = utc_now()
                raise ValueError(f"Index version not found: {new_chunk.index_version_id}")

            bundle = build_index_asset_bundle(
                indexed_document_id=revision.doc_id,
                index_version=version,
                final_doc_id=revision.doc_id,
                canonical_source="chunk_revision",
                chunks=[new_chunk],
            )
            result = __import__("asyncio").run(self.index_backend.write_bundle(bundle))

            # Update in-memory chunks: old chunk unavailable, new chunk active
            for chunk_list in self.chunks_by_index_version.values():
                for i, chunk in enumerate(chunk_list):
                    if chunk.chunk_id == revision.base_evidence_id:
                        chunk.available_int = 0
                        chunk.chunk_data = chunk.chunk_data or {}
                        chunk.chunk_data["superseded_by"] = revision.revision_id
                        break

            self.chunks_by_index_version.setdefault(new_chunk.index_version_id, []).append(new_chunk)

            # Update revision status
            revision.status = "active"
            revision.superseded_evidence_id = revision.base_evidence_id
            revision.updated_at = utc_now()

            return {
                "revision_id": revision_id,
                "status": "active",
                "opensearch_record_count": result.get("opensearch_record_count", 0),
                "qdrant_point_count": result.get("qdrant_point_count", 0),
                "superseded_evidence_id": revision.base_evidence_id,
            }
        except Exception as e:
            revision.status = "failed"
            revision.updated_at = utc_now()
            raise RuntimeError(f"Materialization failed: {e}") from e

    def _apply_chunk_revision(self, base_chunk: ChunkRecord, revision: ChunkRevisionRecord) -> ChunkRecord:
        import uuid
        new_chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
        new_chunk = base_chunk.model_copy(deep=True)
        new_chunk.chunk_id = new_chunk_id
        new_chunk.available_int = 1

        if revision.operation == "delete":
            new_chunk.available_int = 0
        elif revision.operation == "hide":
            new_chunk.available_int = 0
            new_chunk.visibility = "restricted"
        else:
            if revision.content is not None:
                new_chunk.display_text = revision.content
            if revision.vector_text is not None:
                new_chunk.vector_text = revision.vector_text
                new_chunk.embedding_text = revision.vector_text
            if revision.section_path is not None:
                new_chunk.section_path = revision.section_path
            if revision.metadata_patch is not None:
                new_metadata = dict(new_chunk.metadata or {})
                new_metadata.update(revision.metadata_patch)
                new_chunk.metadata = new_metadata
            if revision.citation_payload is not None:
                new_chunk.citation_payload = revision.citation_payload

        # Recompute chunk hash
        new_chunk.chunk_hash = self.stable_chunk_hash(new_chunk.display_text or "")
        return new_chunk

    def save_parse_snapshot(self, snapshot: ParseSnapshotRecord) -> ParseSnapshotRecord:
        session, repos = self._db()
        try:
            repos.parse_snapshot_repo.save(snapshot)
            session.commit()
        finally:
            session.close()
        # DB committed successfully: refresh in-memory projection
        self.parse_snapshots_by_id[snapshot.parse_snapshot_id] = snapshot
        return snapshot

    def get_parse_snapshot(self, parse_snapshot_id: str) -> ParseSnapshotRecord:
        snapshot = self.parse_snapshots_by_id.get(parse_snapshot_id)
        if snapshot is not None:
            return snapshot
        session, repos = self._db()
        try:
            snapshot = repos.parse_snapshot_repo.get(parse_snapshot_id)
        finally:
            session.close()
        if snapshot is None:
            raise KeyError(parse_snapshot_id)
        self.parse_snapshots_by_id[parse_snapshot_id] = snapshot
        return snapshot

    def list_parse_snapshot_chunks(
        self,
        parse_snapshot_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, object]], int]:
        snapshot = self.get_parse_snapshot(parse_snapshot_id)
        page = max(1, int(page))
        page_size = max(1, int(page_size))
        items = [_snapshot_chunk_view(parse_snapshot_id, snapshot, chunk, ordinal) for ordinal, chunk in enumerate(snapshot.upstream_chunks)]
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total

    @staticmethod
    def stable_chunk_hash(content: str) -> str:
        return "sha256:" + sha256(content.encode("utf-8")).hexdigest()

    def mark_job_completed(self, build_job_id: str, *, error_message: str | None = None) -> BuildJobRecord:
        job = self.jobs_by_id[build_job_id]
        new_job = job.model_copy(update={
            "status": IndexBuildStatus.FAILED if error_message else IndexBuildStatus.READY,
            "error_message": error_message,
            "completed_at": utc_now(),
        })
        session, repos = self._db()
        try:
            repos.build_job_repo.complete(
                build_job_id,
                succeeded=not bool(error_message),
                error_message=error_message,
            )
            session.commit()
        finally:
            session.close()
        # DB committed successfully: refresh in-memory projection
        self.jobs_by_id[build_job_id] = new_job
        self.jobs_by_idempotency[new_job.idempotency_key] = new_job
        return new_job

    def _active_version_id(self, collection_id: str) -> str | None:
        session, repos = self._db()
        try:
            registry_entry = repos.index_registry_repo.get(collection_id)
        finally:
            session.close()
        if registry_entry is None:
            return None
        return registry_entry.index_version


def _to_contract_job_state(status: IndexBuildStatus):
    from reality_rag_contracts import IndexBuildJobState

    mapping = {
        IndexBuildStatus.ACCEPTED: IndexBuildJobState.CREATED,
        IndexBuildStatus.RUNNING: IndexBuildJobState.CHUNKING,
        IndexBuildStatus.READY: IndexBuildJobState.SUCCEEDED,
        IndexBuildStatus.FAILED: IndexBuildJobState.FAILED,
    }
    return mapping[status]


def _snapshot_chunk_view(
    parse_snapshot_id: str,
    snapshot: ParseSnapshotRecord,
    chunk: dict[str, object],
    ordinal: int,
) -> dict[str, object]:
    content = str(chunk.get("content_with_weight", "") or "").strip()
    evidence_id = "psc_" + sha256(
        f"{parse_snapshot_id}:{ordinal}:{content}".encode("utf-8")
    ).hexdigest()[:24]
    page_spans = _snapshot_page_spans(chunk)
    first_span = page_spans[0] if page_spans else {"page_from": None, "page_to": None}
    metadata = {
        key: value
        for key, value in chunk.items()
        if key not in {"content_with_weight", "section_path", "page_num_int", "position_int"}
    }
    return {
        "evidence_id": evidence_id,
        "doc_id": snapshot.source_file_id,
        "content": content,
        "section_path": list(chunk.get("section_path", []) or []),
        "page_spans": page_spans,
        "page_from": first_span.get("page_from"),
        "page_to": first_span.get("page_to"),
        "chunk_type": str(chunk.get("doc_type_kwd", "text") or "text"),
        "metadata": metadata,
        "ordinal": ordinal,
    }


def _snapshot_page_spans(chunk: dict[str, object]) -> list[dict[str, int]]:
    page_numbers = [
        int(value)
        for value in list(chunk.get("page_num_int", []) or [])
        if str(value).strip()
    ]
    if page_numbers:
        return [{"page_from": min(page_numbers), "page_to": max(page_numbers)}]
    positions = list(chunk.get("position_int", []) or [])
    extracted_pages: list[int] = []
    for position in positions:
        if isinstance(position, (list, tuple)) and len(position) >= 5:
            try:
                extracted_pages.append(int(position[4]))
            except (TypeError, ValueError):
                continue
    if extracted_pages:
        return [{"page_from": min(extracted_pages), "page_to": max(extracted_pages)}]
    return []


def _synthesize_missing_index_versions(
    *,
    existing: dict[str, IndexVersionRecord],
    registry_entries,
    indexed_documents: list[IndexedDocument],
    chunks: list[ChunkRecord],
    embedding_model: str,
    chunk_profile_id: str = "chunk_default",
) -> list[IndexVersionRecord]:
    registry_by_collection = {entry.collection_id: entry for entry in registry_entries}
    chunks_by_version: dict[str, list[ChunkRecord]] = {}
    docs_by_version: dict[str, list[IndexedDocument]] = {}
    for chunk in chunks:
        chunks_by_version.setdefault(chunk.index_version_id, []).append(chunk)
    for document in indexed_documents:
        docs_by_version.setdefault(document.index_version, []).append(document)

    candidate_ids: set[str] = set(existing.keys())
    for entry in registry_entries:
        candidate_ids.add(entry.index_version)
        if entry.previous_index_version:
            candidate_ids.add(entry.previous_index_version)
        if entry.target_index_version:
            candidate_ids.add(entry.target_index_version)
    candidate_ids.update(chunks_by_version.keys())
    candidate_ids.update(docs_by_version.keys())

    synthesized: list[IndexVersionRecord] = []
    for index_version_id in candidate_ids:
        if not index_version_id or index_version_id in existing:
            continue
        chunk_group = chunks_by_version.get(index_version_id, [])
        doc_group = docs_by_version.get(index_version_id, [])
        collection_id = ""
        tenant_id = ""
        if chunk_group:
            collection_id = chunk_group[0].collection_id
            tenant_id = chunk_group[0].tenant_id
        elif doc_group:
            collection_id = doc_group[0].collection_id
        registry_entry = next(
            (
                entry
                for entry in registry_entries
                if index_version_id in {
                    entry.index_version,
                    entry.previous_index_version,
                    entry.target_index_version,
                }
            ),
            None,
        )
        if registry_entry is not None and not collection_id:
            collection_id = registry_entry.collection_id
        status = IndexVersionStatus.READY
        previous_active_index_version_id = None
        replaced_by_index_version_id = None
        activated_at = None
        if registry_entry is not None:
            if registry_entry.index_version == index_version_id:
                status = IndexVersionStatus.ACTIVE
                previous_active_index_version_id = registry_entry.previous_index_version
                active_docs = [doc for doc in doc_group if doc.state == IndexedDocumentState.ACTIVE]
                if active_docs:
                    activated_at = active_docs[0].activated_at
            elif registry_entry.target_index_version == index_version_id:
                status = IndexVersionStatus.BUILDING if not chunk_group else IndexVersionStatus.READY
            elif registry_entry.previous_index_version == index_version_id:
                status = IndexVersionStatus.INACTIVE
                replaced_by_index_version_id = registry_entry.index_version
        elif not chunk_group:
            status = IndexVersionStatus.BUILDING
        synthesized.append(
            IndexVersionRecord(
                index_version_id=index_version_id,
                tenant_id=tenant_id,
                collection_id=collection_id,
                status=status,
                schema_version="2026-05-26",
                index_profile_id="ragflow",
                chunk_profile_id=chunk_profile_id or "chunk_default",
                embedding_model=embedding_model,
                opensearch_index=f"os_{tenant_id}_{collection_id}_{index_version_id}",
                qdrant_collection=f"qd_{tenant_id}_{collection_id}_{index_version_id}",
                chunk_count=len(chunk_group),
                previous_active_index_version_id=previous_active_index_version_id,
                replaced_by_index_version_id=replaced_by_index_version_id,
                activated_at=activated_at,
            )
        )
    return synthesized
