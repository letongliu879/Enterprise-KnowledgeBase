"""Tests for document-service repositories: upload_sessions, object_blobs,
malware_scan_results, and extended source_files.
"""

from datetime import datetime, timezone

from reality_rag_contracts import (
    ObjectBlobStatus,
    ScanVerdict,
    SourceFileState,
    UploadSessionStatus,
)
from reality_rag_persistence.repositories.malware_scan_results import (
    MalwareScanResultRepository,
)
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.upload_sessions import UploadSessionRepository


class TestUploadSessionRepository:
    def test_create_and_get(self, session):
        repo = UploadSessionRepository(session)
        upl = repo.create(
            upload_id="upl-001",
            source="cli",
            user_id="user-1",
            trace_id="trc-001",
            expected_size=1024,
            expected_sha256="sha256:abc",
        )
        assert upl.upload_id == "upl-001"
        assert upl.source == "cli"
        assert upl.status == "active"
        assert upl.expected_size == 1024

        found = repo.get("upl-001")
        assert found is not None
        assert found.upload_id == "upl-001"

    def test_update_status_to_completed(self, session):
        repo = UploadSessionRepository(session)
        repo.create(upload_id="upl-002")
        updated = repo.update_status("upl-002", UploadSessionStatus.COMPLETED, received_size=2048)
        assert updated is not None
        assert updated.status == "completed"
        assert updated.received_size == 2048
        assert updated.completed_at is not None

    def test_get_nonexistent_returns_none(self, session):
        repo = UploadSessionRepository(session)
        assert repo.get("no-such") is None


class TestObjectBlobRepository:
    def test_create_and_get(self, session):
        repo = ObjectBlobRepository(session)
        obj = repo.create(
            object_id="obj_sha256_abc",
            content_hash="sha256:abc",
            storage_key="s3://bucket/obj_sha256_abc",
            size_bytes=1024,
        )
        assert obj.object_id == "obj_sha256_abc"
        assert obj.content_hash == "sha256:abc"
        assert obj.ref_count == 0
        assert obj.status == "active"

    def test_get_by_content_hash(self, session):
        repo = ObjectBlobRepository(session)
        repo.create("obj_sha256_def", "sha256:def", "s3://bucket/def", 512)
        found = repo.get_by_content_hash("sha256:def")
        assert found is not None
        assert found.object_id == "obj_sha256_def"

    def test_increment_and_decrement_ref(self, session):
        repo = ObjectBlobRepository(session)
        repo.create("obj_sha256_ref", "sha256:ref", "s3://bucket/ref", 100)

        assert repo.increment_ref("obj_sha256_ref") is True
        obj = repo.get("obj_sha256_ref")
        assert obj.ref_count == 1

        assert repo.decrement_ref("obj_sha256_ref") is True
        obj = repo.get("obj_sha256_ref")
        assert obj.ref_count == 0

        # Decrement never goes below 0
        repo.decrement_ref("obj_sha256_ref")
        obj = repo.get("obj_sha256_ref")
        assert obj.ref_count == 0

    def test_mark_gc_pending_and_deleted(self, session):
        repo = ObjectBlobRepository(session)
        repo.create("obj_sha256_gc", "sha256:gc", "s3://bucket/gc", 100)

        repo.mark_gc_pending("obj_sha256_gc")
        obj = repo.get("obj_sha256_gc")
        assert obj.status == "gc_pending"

        repo.mark_deleted("obj_sha256_gc")
        obj = repo.get("obj_sha256_gc")
        assert obj.status == "deleted"
        assert obj.deleted_at is not None

    def test_list_gc_eligible(self, session):
        repo = ObjectBlobRepository(session)
        repo.create("obj_a", "sha256:a", "s3://bucket/a", 100)
        repo.create("obj_b", "sha256:b", "s3://bucket/b", 200)
        repo.increment_ref("obj_b")  # obj_b has ref_count=1

        eligible = repo.list_gc_eligible()
        ids = {o.object_id for o in eligible}
        assert "obj_a" in ids
        assert "obj_b" not in ids


class TestMalwareScanResultRepository:
    def test_create_and_get(self, session):
        repo = MalwareScanResultRepository(session)
        scan = repo.create(
            scan_result_id="scan-001",
            source_file_id="src-001",
            engine="clamav",
            engine_version="1.0.0",
            verdict=ScanVerdict.CLEAN,
        )
        assert scan.scan_result_id == "scan-001"
        assert scan.verdict == "clean"

        found = repo.get("scan-001")
        assert found is not None
        assert found.engine == "clamav"

    def test_update_verdict(self, session):
        repo = MalwareScanResultRepository(session)
        repo.create("scan-002", "src-002", "clamav", "1.0.0")
        updated = repo.update_verdict("scan-002", ScanVerdict.INFECTED, signature="Trojan.XYZ")
        assert updated is not None
        assert updated.verdict == "infected"
        assert updated.signature == "Trojan.XYZ"


class TestSourceFileRepositoryExtended:
    def test_create_with_full_fields(self, session):
        repo = SourceFileRepository(session)
        sf = repo.create(
            source_file_id="src-full-001",
            collection_id="col-1",
            object_id="obj_sha256_full",
            content_hash="sha256:full",
            upload_id="upl-full",
            visibility="EXTERNAL",
            original_name="report.pdf",
            sanitized_name="report_pdf",
            size_bytes=4096,
            state=SourceFileState.UPLOADING,
        )
        assert sf.upload_id == "upl-full"
        assert sf.visibility == "EXTERNAL"
        assert sf.original_name == "report.pdf"
        assert sf.sanitized_name == "report_pdf"
        assert sf.size_bytes == 4096
        assert sf.state == SourceFileState.UPLOADING

    def test_update_state_and_scan_result(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-state-001", "col-1", "obj_state", "sha256:state")
        updated = repo.update_state("src-state-001", SourceFileState.SCANNING, scan_result_id="scan-001")
        assert updated is not None
        assert updated.state == SourceFileState.SCANNING
        assert updated.scan_result_id == "scan-001"

    def test_mark_cleaned_from_cleanable(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-clean-001", "col-1", "obj_clean", "sha256:clean")
        repo.claim("src-clean-001", "job-1")
        repo.mark_consumed("src-clean-001", "job-1")
        repo.mark_cleanable("src-clean-001", "job-1")

        assert repo.mark_cleaned("src-clean-001") is True
        sf = repo.get("src-clean-001")
        assert sf.state == SourceFileState.CLEANED

    def test_mark_cleaned_fails_from_non_cleanable(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-clean-002", "col-1", "obj_clean2", "sha256:clean2")
        assert repo.mark_cleaned("src-clean-002") is False

    def test_mark_failed(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-fail-001", "col-1", "obj_fail", "sha256:fail")
        assert repo.mark_failed("src-fail-001") is True
        sf = repo.get("src-fail-001")
        assert sf.state == SourceFileState.FAILED

    def test_list_by_object_id(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-obj-a1", "col-1", "obj_shared", "sha256:shared")
        repo.create("src-obj-a2", "col-2", "obj_shared", "sha256:shared")

        sfs = repo.list_by_object_id("obj_shared")
        assert len(sfs) == 2

    def test_count_active_by_object_id(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-act-1", "col-1", "obj_count", "sha256:count")
        repo.create("src-act-2", "col-2", "obj_count", "sha256:count")
        # Mark one cleanable (non-active)
        repo.claim("src-act-2", "job-1")
        repo.mark_cleanable("src-act-2", "job-1")

        assert repo.count_active_by_object_id("obj_count") == 1

    def test_find_active_by_content_hash_ignores_cleanable(self, session):
        repo = SourceFileRepository(session)
        repo.create("src-cleanable", "col-1", "obj-cleanable", "sha256:cleanable")
        repo.claim("src-cleanable", "job-1")
        repo.mark_cleanable("src-cleanable", "job-1")

        assert repo.find_active_by_content_hash("sha256:cleanable", "col-1") is None
