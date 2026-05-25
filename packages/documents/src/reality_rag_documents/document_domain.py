"""Document domain — source file lifecycle, object storage, and dedup.

Owner: document-service (in monolith: document_domain module).

This module contains:
  - DocumentService: manages upload_sessions, object_blobs, source_files,
    malware_scan_results, and dedup queries.
  - ScanAdapter (stub): interface for malware scanning; production plugs in
    a real scan engine.

Rules:
  - DocumentService does NOT write documents, policies, or index state.
  - DocumentService does NOT advance intake_job_state.
  - Object deletion MUST check ref_count via ObjectBlobRepository.
  - CLEANABLE != physical deletion. CLEANED means source_file reference
    is released; object bytes are only deleted when ref_count == 0.
  - (content_hash, collection_id) active partial unique is enforced by DB.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from reality_rag_contracts import (
    EventType,
    MalwareScanResult,
    ObjectBlob,
    ObjectBlobStatus,
    ScanVerdict,
    SourceFile,
    SourceFileState,
    UploadSession,
    UploadSessionStatus,
)
from reality_rag_persistence.repositories.object_blobs import ObjectBlobRepository
from reality_rag_persistence.repositories.source_files import SourceFileRepository
from reality_rag_persistence.repositories.upload_sessions import UploadSessionRepository

from reality_rag_persistence.outbox import EventPublisher

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ── Scan Adapter (stub) ─────────────────────────────────────────────────


class ScanAdapter(Protocol):
    """Pluggable malware scan adapter."""

    def scan(self, storage_key: str) -> MalwareScanResult:
        """Scan the object at storage_key and return a scan result."""
        ...


class NoOpScanAdapter:
    """No-op scan adapter — always returns CLEAN."""

    def scan(self, storage_key: str) -> MalwareScanResult:
        return MalwareScanResult(
            scan_result_id=_generate_scan_result_id(),
            source_file_id="",
            engine="noop",
            engine_version="0.0.0",
            verdict=ScanVerdict.CLEAN,
            scanned_at=datetime.now(timezone.utc),
        )


# ── Document Service ─────────────────────────────────────────────────────


class DocumentService:
    """Document-service domain logic for source file lifecycle.

    Owner: document-service.
    """

    def __init__(
        self,
        session: Session,
        scan_adapter: ScanAdapter | None = None,
    ) -> None:
        self._session = session
        self._upload_repo = UploadSessionRepository(session)
        self._object_repo = ObjectBlobRepository(session)
        self._source_repo = SourceFileRepository(session)
        self._scan_adapter = scan_adapter or NoOpScanAdapter()
        self._event_publisher = EventPublisher(session)

    # ------------------------------------------------------------------
    # Upload session
    # ------------------------------------------------------------------

    def create_upload_session(
        self,
        source: str = "web",
        user_id: str | None = None,
        trace_id: str = "",
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> UploadSession:
        """Create a new upload session in ACTIVE state."""
        upload_id = _generate_upload_id()
        return self._upload_repo.create(
            upload_id=upload_id,
            source=source,
            user_id=user_id,
            trace_id=trace_id,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )

    def complete_upload_session(
        self,
        upload_id: str,
        received_size: int,
    ) -> UploadSession | None:
        """Mark upload session as completed."""
        return self._upload_repo.update_status(
            upload_id=upload_id,
            status=UploadSessionStatus.COMPLETED,
            received_size=received_size,
        )

    # ------------------------------------------------------------------
    # Object blob
    # ------------------------------------------------------------------

    def get_or_create_object_blob(
        self,
        content_hash: str,
        storage_key: str,
        size_bytes: int = 0,
    ) -> ObjectBlob:
        """Get existing object blob by content_hash, or create a new one.

        Returns the existing object if content_hash already exists.
        """
        existing = self._object_repo.get_by_content_hash(content_hash)
        if existing is not None:
            return existing

        object_id = _object_id_from_hash(content_hash)
        return self._object_repo.create(
            object_id=object_id,
            content_hash=content_hash,
            storage_key=storage_key,
            size_bytes=size_bytes,
        )

    def link_object_ref(self, object_id: str) -> bool:
        """Increment object ref_count when a source_file references it."""
        return self._object_repo.increment_ref(object_id)

    def unlink_object_ref(self, object_id: str) -> bool:
        """Decrement object ref_count when a source_file is cleaned."""
        return self._object_repo.decrement_ref(object_id)

    def gc_object_blob(self, object_id: str) -> bool:
        """Garbage-collect an object blob if ref_count is 0.

        Returns True if the object was marked deleted.
        Does NOT delete bytes from storage — that is a storage-layer concern.
        """
        obj = self._object_repo.get(object_id)
        if obj is None:
            return False
        if obj.ref_count > 0:
            return False
        if obj.status == ObjectBlobStatus.DELETED.value:
            return True
        self._object_repo.mark_gc_pending(object_id)
        # In production, storage deletion would happen here or asynchronously.
        self._object_repo.mark_deleted(object_id)
        return True

    # ------------------------------------------------------------------
    # Source file
    # ------------------------------------------------------------------

    def create_source_file(
        self,
        collection_id: str,
        object_id: str,
        content_hash: str,
        *,
        upload_id: str | None = None,
        visibility: str = "INTERNAL",
        original_name: str = "",
        sanitized_name: str = "",
        size_bytes: int = 0,
        state: SourceFileState = SourceFileState.READY,
    ) -> SourceFile:
        """Create a new source file record.

        Raises ValueError if an active source file already exists for
        (content_hash, collection_id).
        """
        # Check active dedup before creating
        existing_active = self._source_repo.find_active_by_content_hash(
            content_hash, collection_id
        )
        if existing_active is not None:
            raise ValueError(
                f"Active source file already exists: {existing_active.source_file_id}"
            )

        source_file_id = _generate_source_file_id()
        sf = self._source_repo.create(
            source_file_id=source_file_id,
            collection_id=collection_id,
            object_id=object_id,
            content_hash=content_hash,
            upload_id=upload_id,
            visibility=visibility,
            original_name=original_name,
            sanitized_name=sanitized_name,
            size_bytes=size_bytes,
            state=state,
        )
        # Link object ref
        self._object_repo.increment_ref(object_id)

        # Phase 7: emit FileReady outbox if already in READY state
        if state == SourceFileState.READY:
            self._emit_file_ready(sf)

        return sf

    def claim_source_file(self, source_file_id: str, job_id: str) -> bool:
        """Claim a source file for an intake job.

        Only READY files can be claimed.
        """
        return self._source_repo.claim(source_file_id, job_id)

    def mark_consumed(self, source_file_id: str, job_id: str) -> bool:
        """Mark source file as consumed after conversion reads it."""
        return self._source_repo.mark_consumed(source_file_id, job_id)

    def mark_cleanable(self, source_file_id: str, job_id: str) -> bool:
        """Mark source file as cleanable (GC eligible) after job reaches terminal state."""
        return self._source_repo.mark_cleanable(source_file_id, job_id)

    def gc_source_file(self, source_file_id: str) -> bool:
        """Clean a source_file and decrement its object ref.

        Returns True if the source_file was marked CLEANED.
        After this, caller may call gc_object_blob() if ref_count == 0.
        """
        sf = self._source_repo.get(source_file_id)
        if sf is None or sf.state != SourceFileState.CLEANABLE:
            return False

        # Mark source file cleaned
        ok = self._source_repo.mark_cleaned(source_file_id)
        if not ok:
            return False

        # Unlink object ref
        self._object_repo.decrement_ref(sf.object_id)
        return True

    def release_claim(self, source_file_id: str) -> bool:
        """Release a claim back to READY (e.g. job cancelled before conversion)."""
        return self._source_repo.release_claim(source_file_id)

    # ------------------------------------------------------------------
    # Scan lifecycle
    # ------------------------------------------------------------------

    def start_scan(self, source_file_id: str) -> SourceFile | None:
        """Mark source file as SCANNING."""
        return self._source_repo.update_state(
            source_file_id, SourceFileState.SCANNING
        )

    def complete_scan(self, source_file_id: str) -> SourceFile | None:
        """Run malware scan and mark source file as READY or FAILED.

        Uses the configured scan_adapter. In production this may be async.
        """
        sf = self._source_repo.get(source_file_id)
        if sf is None or sf.state != SourceFileState.SCANNING:
            return None

        # Run scan via adapter
        obj = self._object_repo.get(sf.object_id)
        if obj is None:
            self._source_repo.update_state(source_file_id, SourceFileState.FAILED)
            return None

        scan_result = self._scan_adapter.scan(obj.storage_key)
        # Attach source_file_id to the result
        scan_result.source_file_id = source_file_id

        # Persist scan result
        from reality_rag_persistence.repositories.malware_scan_results import (
            MalwareScanResultRepository,
        )

        scan_repo = MalwareScanResultRepository(self._session)
        persisted = scan_repo.create(
            scan_result_id=scan_result.scan_result_id,
            source_file_id=source_file_id,
            engine=scan_result.engine,
            engine_version=scan_result.engine_version,
            verdict=ScanVerdict(scan_result.verdict),
            signature=scan_result.signature,
            raw_result_ref=scan_result.raw_result_ref,
        )

        # Transition based on verdict
        if persisted.verdict == ScanVerdict.CLEAN.value:
            sf = self._source_repo.update_state(
                source_file_id, SourceFileState.READY, scan_result_id=persisted.scan_result_id
            )
            if sf is not None:
                self._emit_file_ready(sf)
            return sf
        else:
            return self._source_repo.update_state(
                source_file_id, SourceFileState.FAILED, scan_result_id=persisted.scan_result_id
            )

    # ------------------------------------------------------------------
    # Dedup queries
    # ------------------------------------------------------------------

    def dedup_check(
        self,
        content_hash: str,
        collection_id: str,
        document_repo,
    ) -> tuple[bool, str | None]:
        """Check for duplicate upload.

        Returns (is_duplicate, existing_doc_id):
          - Primary: published document by source_content_hash
          - Secondary: active sourceFile in the same collection
        """
        # Primary: published document dedup (survives source file cleanup)
        existing_doc = document_repo.get_by_source_content_hash(
            content_hash, collection_id
        )
        if existing_doc is not None:
            return True, existing_doc.doc_id

        # Secondary: active source file in same collection
        existing_sf = self._source_repo.find_active_by_content_hash(
            content_hash, collection_id
        )
        if existing_sf is not None:
            return True, None  # duplicate upload, but no published doc yet

        return False, None

    def _emit_file_ready(self, sf: SourceFile) -> None:
        """Emit FileReady outbox event for a READY source file."""
        self._event_publisher.publish(
            event_type=EventType.FILE_READY,
            aggregate_type="source_file",
            aggregate_id=sf.source_file_id,
            payload={
                "source_file_id": sf.source_file_id,
                "object_id": sf.object_id,
                "content_hash": sf.content_hash,
                "collection_id": sf.collection_id,
                "visibility": sf.visibility,
                "original_name": sf.original_name,
                "size_bytes": sf.size_bytes,
            },
            trace_id=sf.upload_id or "",
        )


# ------------------------------------------------------------------
# ID generators
# ------------------------------------------------------------------

_UPLOAD_PREFIX = "upl_"
_SRC_PREFIX = "src_"
_SCAN_PREFIX = "scan_"


def _generate_upload_id() -> str:
    return _UPLOAD_PREFIX + secrets.token_hex(12)


def _generate_source_file_id() -> str:
    return _SRC_PREFIX + secrets.token_hex(12)


def _generate_scan_result_id() -> str:
    return _SCAN_PREFIX + secrets.token_hex(12)


def _object_id_from_hash(content_hash: str) -> str:
    """Generate object_id from content_hash.

    Strips any prefix (e.g. 'sha256:') and uses the hex digest.
    """
    # Remove any prefix like 'sha256:'
    if ":" in content_hash:
        content_hash = content_hash.split(":", 1)[1]
    return f"obj_sha256_{content_hash}"
