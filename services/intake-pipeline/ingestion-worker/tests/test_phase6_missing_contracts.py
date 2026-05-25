"""Phase 6 publishing/indexing repository lifecycle tests.

These tests replace the previous negative gap-enumeration tests.
They exercise the 6 core Phase 6 repositories through create-read-update
lifecycles to ensure the publishing/indexing boundary is fully implemented.
"""

from __future__ import annotations

from reality_rag_contracts import (
    IndexBuildJobState,
    IndexedDocumentState,
    PublishJobState,
    PublishedDocumentState,
    ReindexJobState,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.index_build_jobs import (
    IndexBuildJobRepository,
)
from reality_rag_persistence.repositories.indexed_documents import (
    IndexedDocumentRepository,
)
from reality_rag_persistence.repositories.publish_jobs import PublishJobRepository
from reality_rag_persistence.repositories.published_document_lifecycle_audit import (
    PublishedDocumentLifecycleAuditRepository,
)
from reality_rag_persistence.repositories.published_documents import (
    PublishedDocumentRepository,
)
from reality_rag_persistence.repositories.reindex_jobs import ReindexJobRepository


class TestPublishedDocumentRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = PublishedDocumentRepository(session)
        doc = repo.create(
            published_document_id="pd-001",
            final_doc_id="fd-001",
            logical_document_id="ld-001",
            tenant_id="t-1",
            collection_id="col-1",
            version=1,
            source_content_hash="sha256:abc",
            canonical_hash="sha256:canon",
            state=PublishedDocumentState.PUBLISHED,
            active_index_version="v1",
            created_by_ticket_id="ticket-1",
            asset_paths={"json": "s3://bucket/doc.json"},
        )
        assert doc.published_document_id == "pd-001"
        assert doc.state == PublishedDocumentState.PUBLISHED
        assert doc.active_index_version == "v1"

        found = repo.get("pd-001")
        assert found is not None
        assert found.final_doc_id == "fd-001"

    def test_get_by_final_doc_id(self):
        session = get_session()
        repo = PublishedDocumentRepository(session)
        repo.create("pd-002", "fd-002", "ld-002", "t-1", "col-1", 1)
        found = repo.get_by_final_doc_id("fd-002")
        assert found is not None
        assert found.published_document_id == "pd-002"

    def test_list_by_collection(self):
        session = get_session()
        repo = PublishedDocumentRepository(session)
        repo.create("pd-003", "fd-003", "ld-003", "t-1", "col-a", 1)
        repo.create("pd-004", "fd-004", "ld-004", "t-1", "col-a", 1)
        repo.create("pd-005", "fd-005", "ld-005", "t-1", "col-b", 1)
        docs = repo.list_by_collection("col-a")
        assert len(docs) == 2

    def test_update_state(self):
        session = get_session()
        repo = PublishedDocumentRepository(session)
        repo.create("pd-006", "fd-006", "ld-006", "t-1", "col-1", 1)
        ok = repo.update_state("pd-006", PublishedDocumentState.ARCHIVED)
        assert ok is True
        doc = repo.get("pd-006")
        assert doc.state == PublishedDocumentState.ARCHIVED
        assert doc.previous_state == "published"

    def test_set_active_index_version(self):
        session = get_session()
        repo = PublishedDocumentRepository(session)
        repo.create("pd-007", "fd-007", "ld-007", "t-1", "col-1", 1)
        ok = repo.set_active_index_version("pd-007", "v2")
        assert ok is True
        doc = repo.get("pd-007")
        assert doc.active_index_version == "v2"


class TestPublishedDocumentLifecycleAuditRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = PublishedDocumentLifecycleAuditRepository(session)
        audit = repo.create(
            audit_id="audit-001",
            published_document_id="pd-001",
            final_doc_id="fd-001",
            actor_id="user-1",
            action="publish",
            before_state="draft",
            after_state="published",
            reason="Approved by ticket-1",
            payload_hash="sha256:payload",
        )
        assert audit.audit_id == "audit-001"
        assert audit.action == "publish"

        found = repo.get("audit-001")
        assert found is not None
        assert found.before_state == "draft"

    def test_list_by_published_document(self):
        session = get_session()
        repo = PublishedDocumentLifecycleAuditRepository(session)
        repo.create("audit-002", "pd-010", "fd-010", "sys", "publish")
        repo.create("audit-003", "pd-010", "fd-010", "sys", "archive")
        repo.create("audit-004", "pd-011", "fd-011", "sys", "publish")
        entries = repo.list_by_published_document("pd-010")
        assert len(entries) == 2
        assert entries[0].action == "publish"
        assert entries[1].action == "archive"


class TestPublishJobRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = PublishJobRepository(session)
        job = repo.create(
            publish_id="pub-001",
            intake_job_id="intake-001",
            final_doc_id="fd-001",
            collection_id="col-1",
        )
        assert job.publish_id == "pub-001"
        assert job.state == PublishJobState.CREATED

        found = repo.get("pub-001")
        assert found is not None
        assert found.intake_job_id == "intake-001"

    def test_list_by_collection(self):
        session = get_session()
        repo = PublishJobRepository(session)
        repo.create("pub-002", "intake-002", "fd-002", "col-a")
        repo.create("pub-003", "intake-003", "fd-003", "col-a")
        jobs = repo.list_by_collection("col-a")
        assert len(jobs) == 2

    def test_update_state(self):
        session = get_session()
        repo = PublishJobRepository(session)
        repo.create("pub-004", "intake-004", "fd-004", "col-1")
        ok = repo.update_state("pub-004", PublishJobState.ASSET_WRITING, stage="asset_writing")
        assert ok is True
        job = repo.get("pub-004")
        assert job.state == PublishJobState.ASSET_WRITING
        assert job.stage == "asset_writing"

    def test_complete_success(self):
        session = get_session()
        repo = PublishJobRepository(session)
        repo.create("pub-005", "intake-005", "fd-005", "col-1")
        ok = repo.complete("pub-005", succeeded=True)
        assert ok is True
        job = repo.get("pub-005")
        assert job.state == PublishJobState.SUCCEEDED
        assert job.completed_at is not None

    def test_complete_failure(self):
        session = get_session()
        repo = PublishJobRepository(session)
        repo.create("pub-006", "intake-006", "fd-006", "col-1")
        ok = repo.complete("pub-006", succeeded=False, error_message="S3 write failed")
        assert ok is True
        job = repo.get("pub-006")
        assert job.state == PublishJobState.FAILED
        assert job.error_message == "S3 write failed"


class TestReindexJobRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = ReindexJobRepository(session)
        job = repo.create(
            reindex_job_id="reidx-001",
            final_doc_id="fd-001",
            collection_id="col-1",
            source_index_version="v1",
            target_index_version="v2",
        )
        assert job.reindex_job_id == "reidx-001"
        assert job.state == ReindexJobState.CREATED
        assert job.target_index_version == "v2"

        found = repo.get("reidx-001")
        assert found is not None

    def test_update_state(self):
        session = get_session()
        repo = ReindexJobRepository(session)
        repo.create("reidx-002", "fd-002", "col-1", "v1", "v2")
        ok = repo.update_state("reidx-002", ReindexJobState.INDEX_BUILDING)
        assert ok is True
        job = repo.get("reidx-002")
        assert job.state == ReindexJobState.INDEX_BUILDING

    def test_complete(self):
        session = get_session()
        repo = ReindexJobRepository(session)
        repo.create("reidx-003", "fd-003", "col-1", "v1", "v2")
        ok = repo.complete("reidx-003", succeeded=True)
        assert ok is True
        job = repo.get("reidx-003")
        assert job.state == ReindexJobState.SUCCEEDED
        assert job.completed_at is not None


class TestIndexBuildJobRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = IndexBuildJobRepository(session)
        job = repo.create(
            index_build_job_id="ibj-001",
            collection_id="col-1",
            target_index_version="v2",
            publish_id="pub-001",
        )
        assert job.index_build_job_id == "ibj-001"
        assert job.state == IndexBuildJobState.CREATED
        assert job.chunk_count == 0

        found = repo.get("ibj-001")
        assert found is not None
        assert found.publish_id == "pub-001"

    def test_list_by_collection(self):
        session = get_session()
        repo = IndexBuildJobRepository(session)
        repo.create("ibj-002", "col-a", "v2")
        repo.create("ibj-003", "col-a", "v3")
        jobs = repo.list_by_collection("col-a")
        assert len(jobs) == 2

    def test_update_state(self):
        session = get_session()
        repo = IndexBuildJobRepository(session)
        repo.create("ibj-004", "col-1", "v2")
        ok = repo.update_state("ibj-004", IndexBuildJobState.EMBEDDING)
        assert ok is True
        job = repo.get("ibj-004")
        assert job.state == IndexBuildJobState.EMBEDDING

    def test_update_progress(self):
        session = get_session()
        repo = IndexBuildJobRepository(session)
        repo.create("ibj-005", "col-1", "v2")
        ok = repo.update_progress("ibj-005", chunk_count=42, embedding_count=40)
        assert ok is True
        job = repo.get("ibj-005")
        assert job.chunk_count == 42
        assert job.embedding_count == 40

    def test_complete(self):
        session = get_session()
        repo = IndexBuildJobRepository(session)
        repo.create("ibj-006", "col-1", "v2")
        ok = repo.complete("ibj-006", succeeded=False, error_message="Qdrant timeout")
        assert ok is True
        job = repo.get("ibj-006")
        assert job.state == IndexBuildJobState.FAILED
        assert job.error_message == "Qdrant timeout"
        assert job.completed_at is not None


class TestIndexedDocumentRepository:
    def test_create_and_get(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        idx = repo.create(
            indexed_document_id="idx-001",
            final_doc_id="fd-001",
            collection_id="col-1",
            index_version="v2",
            chunk_count=10,
            embedding_count=10,
            state=IndexedDocumentState.CANDIDATE,
        )
        assert idx.indexed_document_id == "idx-001"
        assert idx.state == IndexedDocumentState.CANDIDATE

        found = repo.get("idx-001")
        assert found is not None
        assert found.chunk_count == 10

    def test_get_by_final_doc_and_version(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-002", "fd-002", "col-1", "v2")
        found = repo.get_by_final_doc_and_version("fd-002", "v2")
        assert found is not None
        assert found.indexed_document_id == "idx-002"

    def test_list_by_collection(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-003", "fd-003", "col-a", "v2")
        repo.create("idx-004", "fd-004", "col-a", "v2")
        repo.create("idx-005", "fd-005", "col-b", "v2")
        docs = repo.list_by_collection("col-a")
        assert len(docs) == 2

    def test_list_by_collection_and_version(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-006", "fd-006", "col-a", "v1")
        repo.create("idx-007", "fd-007", "col-a", "v2")
        docs = repo.list_by_collection("col-a", index_version="v1")
        assert len(docs) == 1
        assert docs[0].index_version == "v1"

    def test_activate(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-008", "fd-008", "col-1", "v2")
        ok = repo.activate("idx-008")
        assert ok is True
        doc = repo.get("idx-008")
        assert doc.state == IndexedDocumentState.ACTIVE
        assert doc.activated_at is not None

    def test_update_counts(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-009", "fd-009", "col-1", "v2")
        ok = repo.update_counts("idx-009", chunk_count=20, embedding_count=18)
        assert ok is True
        doc = repo.get("idx-009")
        assert doc.chunk_count == 20
        assert doc.embedding_count == 18

    def test_update_state(self):
        session = get_session()
        repo = IndexedDocumentRepository(session)
        repo.create("idx-010", "fd-010", "col-1", "v2")
        ok = repo.update_state("idx-010", IndexedDocumentState.TOMBSTONED)
        assert ok is True
        doc = repo.get("idx-010")
        assert doc.state == IndexedDocumentState.TOMBSTONED
