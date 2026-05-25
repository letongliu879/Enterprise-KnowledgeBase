"""Tests for document_domain — DocumentService, object lifecycle, dedup, GC."""

from __future__ import annotations

import pytest

from reality_rag_contracts import (
    ObjectBlobStatus,
    ScanVerdict,
    SourceFileState,
    UploadSessionStatus,
)
from reality_rag_persistence.database import get_session
from reality_rag_persistence.repositories.collections import CollectionRepository
from reality_rag_persistence.repositories.documents import DocumentRepository
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.tenants import TenantRepository
from reality_rag_persistence.repositories.upload_sessions import UploadSessionRepository

from ingestion_worker.domains.document_domain import DocumentService, _object_id_from_hash


class TestObjectIdFromHash:
    def test_strips_sha256_prefix(self):
        assert _object_id_from_hash("sha256:abcd1234") == "obj_sha256_abcd1234"

    def test_plain_hash_unchanged(self):
        assert _object_id_from_hash("abcd1234") == "obj_sha256_abcd1234"


class TestDocumentServiceUploadSession:
    def test_create_upload_session(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            upl = svc.create_upload_session(source="cli", user_id="u-1", trace_id="trc-1")
            assert upl.source == "cli"
            assert upl.user_id == "u-1"
            assert upl.status == UploadSessionStatus.ACTIVE.value

            found = UploadSessionRepository(session).get(upl.upload_id)
            assert found is not None
            assert found.upload_id == upl.upload_id
        finally:
            session.close()

    def test_complete_upload_session(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            upl = svc.create_upload_session()
            completed = svc.complete_upload_session(upl.upload_id, received_size=2048)
            assert completed is not None
            assert completed.status == UploadSessionStatus.COMPLETED.value
            assert completed.received_size == 2048
        finally:
            session.close()


class TestDocumentServiceObjectBlob:
    def test_get_or_create_creates_new(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:new", "s3://bucket/new", 100)
            assert obj.content_hash == "sha256:new"
            assert obj.ref_count == 0
            assert obj.status == ObjectBlobStatus.ACTIVE.value
        finally:
            session.close()

    def test_get_or_create_returns_existing(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            obj1 = svc.get_or_create_object_blob("sha256:dup", "s3://bucket/dup", 100)
            obj2 = svc.get_or_create_object_blob("sha256:dup", "s3://bucket/other", 200)
            assert obj1.object_id == obj2.object_id
            assert obj2.storage_key == "s3://bucket/dup"  # original storage_key kept
        finally:
            session.close()

    def test_link_and_unlink_ref(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:ref", "s3://bucket/ref", 50)
            svc.link_object_ref(obj.object_id)
            updated = ObjectBlobRepository(session).get(obj.object_id)
            assert updated.ref_count == 1

            svc.unlink_object_ref(obj.object_id)
            updated = ObjectBlobRepository(session).get(obj.object_id)
            assert updated.ref_count == 0
        finally:
            session.close()

    def test_gc_object_blob_with_zero_ref(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:gc", "s3://bucket/gc", 10)
            assert svc.gc_object_blob(obj.object_id) is True
            updated = ObjectBlobRepository(session).get(obj.object_id)
            assert updated.status == ObjectBlobStatus.DELETED.value
        finally:
            session.close()

    def test_gc_object_blob_with_nonzero_ref_fails(self):
        session = get_session()
        try:
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:gc2", "s3://bucket/gc2", 10)
            svc.link_object_ref(obj.object_id)
            assert svc.gc_object_blob(obj.object_id) is False
            updated = ObjectBlobRepository(session).get(obj.object_id)
            assert updated.status == ObjectBlobStatus.ACTIVE.value
        finally:
            session.close()


class TestDocumentServiceSourceFile:
    def _seed_collection(self, session, collection_id: str = "col-doc"):
        if TenantRepository(session).get("default") is None:
            TenantRepository(session).save(
                __import__("reality_rag_contracts").Tenant(tenant_id="default", name="Default")
            )
        if CollectionRepository(session).get(collection_id) is None:
            CollectionRepository(session).save(
                __import__("reality_rag_contracts").Collection(
                    collection_id=collection_id,
                    tenant_id="default",
                    name="Doc Collection",
                    authority_level=5,
                )
            )
        session.commit()

    def test_create_source_file(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:sf", "s3://bucket/sf", 100)
            sf = svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:sf",
                original_name="report.pdf",
                size_bytes=100,
            )
            assert sf.collection_id == "col-doc"
            assert sf.state == SourceFileState.READY
            assert sf.original_name == "report.pdf"
            # Object ref should be incremented
            obj_updated = ObjectBlobRepository(session).get(obj.object_id)
            assert obj_updated.ref_count == 1
        finally:
            session.close()

    def test_create_source_file_rejects_duplicate_active(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:dup2", "s3://bucket/dup2", 100)
            svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:dup2",
            )
            with pytest.raises(ValueError, match="Active source file already exists"):
                svc.create_source_file(
                    collection_id="col-doc",
                    object_id=obj.object_id,
                    content_hash="sha256:dup2",
                )
        finally:
            session.close()

    def test_claim_and_mark_consumed(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:claim", "s3://bucket/claim", 100)
            sf = svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:claim",
            )
            assert svc.claim_source_file(sf.source_file_id, "job-1") is True
            assert svc.mark_consumed(sf.source_file_id, "job-1") is True

            updated = SourceFileRepository(session).get(sf.source_file_id)
            assert updated.state == SourceFileState.CONSUMED
            assert updated.claimed_by_job_id == "job-1"
        finally:
            session.close()

    def test_mark_cleanable_and_gc(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:clean", "s3://bucket/clean", 100)
            sf = svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:clean",
            )
            svc.claim_source_file(sf.source_file_id, "job-1")
            svc.mark_consumed(sf.source_file_id, "job-1")

            assert svc.mark_cleanable(sf.source_file_id, "job-1") is True
            sf_updated = SourceFileRepository(session).get(sf.source_file_id)
            assert sf_updated.state == SourceFileState.CLEANABLE

            # GC source file should decrement object ref
            assert svc.gc_source_file(sf.source_file_id) is True
            sf_cleaned = SourceFileRepository(session).get(sf.source_file_id)
            assert sf_cleaned.state == SourceFileState.CLEANED

            obj_updated = ObjectBlobRepository(session).get(obj.object_id)
            assert obj_updated.ref_count == 0

            # Now object can be GC'd
            assert svc.gc_object_blob(obj.object_id) is True
        finally:
            session.close()

    def test_release_claim(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:rel", "s3://bucket/rel", 100)
            sf = svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:rel",
            )
            svc.claim_source_file(sf.source_file_id, "job-1")
            assert svc.release_claim(sf.source_file_id) is True
            updated = SourceFileRepository(session).get(sf.source_file_id)
            assert updated.state == SourceFileState.READY
            assert updated.claimed_by_job_id is None
        finally:
            session.close()

    def test_scan_lifecycle(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:scan", "s3://bucket/scan", 100)
            sf = svc.create_source_file(
                collection_id="col-doc",
                object_id=obj.object_id,
                content_hash="sha256:scan",
                state=SourceFileState.UPLOADED,
            )
            # Start scan
            updated = svc.start_scan(sf.source_file_id)
            assert updated is not None
            assert updated.state == SourceFileState.SCANNING

            # Complete scan (with noop adapter, always CLEAN)
            completed = svc.complete_scan(sf.source_file_id)
            assert completed is not None
            assert completed.state == SourceFileState.READY
            assert completed.scan_result_id is not None
        finally:
            session.close()


class TestDocumentServiceDedup:
    def _seed_collection(self, session, collection_id: str = "col-dedup"):
        if TenantRepository(session).get("default") is None:
            TenantRepository(session).save(
                __import__("reality_rag_contracts").Tenant(tenant_id="default", name="Default")
            )
        if CollectionRepository(session).get(collection_id) is None:
            CollectionRepository(session).save(
                __import__("reality_rag_contracts").Collection(
                    collection_id=collection_id,
                    tenant_id="default",
                    name="Dedup Collection",
                    authority_level=5,
                )
            )
        session.commit()

    def test_dedup_finds_published_document(self):
        session = get_session()
        try:
            self._seed_collection(session)
            doc_repo = DocumentRepository(session)
            doc_repo.save(
                __import__("reality_rag_contracts").CanonicalMetadata(
                    doc_id="doc-dedup-1",
                    logical_document_id="ldoc-dedup-1",
                    tenant_id="default",
                    collection_id="col-dedup",
                    source_hash="sha256:dedup",
                    source_content_hash="sha256:dedup",
                    version=1,
                    publish_status=__import__("reality_rag_contracts").PublishStatus.PUBLISHED,
                    index_status=__import__("reality_rag_contracts").IndexStatus.INDEXED,
                )
            )
            session.commit()

            svc = DocumentService(session)
            is_dup, existing_doc_id = svc.dedup_check("sha256:dedup", "col-dedup", doc_repo)
            assert is_dup is True
            assert existing_doc_id == "doc-dedup-1"
        finally:
            session.close()

    def test_dedup_finds_active_source_file(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            obj = svc.get_or_create_object_blob("sha256:act", "s3://bucket/act", 100)
            svc.create_source_file(
                collection_id="col-dedup",
                object_id=obj.object_id,
                content_hash="sha256:act",
            )
            doc_repo = DocumentRepository(session)
            is_dup, existing_doc_id = svc.dedup_check("sha256:act", "col-dedup", doc_repo)
            assert is_dup is True
            assert existing_doc_id is None  # no published doc, but active source file exists
        finally:
            session.close()

    def test_dedup_no_duplicate(self):
        session = get_session()
        try:
            self._seed_collection(session)
            svc = DocumentService(session)
            doc_repo = DocumentRepository(session)
            is_dup, existing_doc_id = svc.dedup_check("sha256:new", "col-dedup", doc_repo)
            assert is_dup is False
            assert existing_doc_id is None
        finally:
            session.close()
